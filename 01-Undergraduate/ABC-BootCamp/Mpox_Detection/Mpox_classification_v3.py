"""Stage 3 (research): 3 learning rates x 3 dropout rates, based on stage-2 VGG19.

Nine candidates are independently loaded and trained. They are NOT selected for
Android deployment because the project's mobile footprint/latency constraints
favoured a single stage-2 model. Optional ensemble evaluation is exploratory.
"""
from __future__ import annotations

import argparse
import gc
import json
from pathlib import Path

import numpy as np
import tensorflow as tf
from tensorflow.keras.preprocessing.image import ImageDataGenerator

LEARNING_RATES = (0.001, 0.0001, 0.01)  # Historically tested. 0.01 may be unstable.
DROPOUT_RATES = (0.2, 0.3, 0.4)


def get_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description='Stage 3 - non-deployed model candidates')
    parser.add_argument('--data-root', type=Path, default=Path('Mpox/Fold1/Fold1/Fold1'))
    parser.add_argument('--base-model', type=Path,
                        default=Path('models/monkeypox_classification_model2.keras'))
    parser.add_argument('--output-dir', type=Path, default=Path('models/experiments'))
    parser.add_argument('--epochs', type=int, default=10)
    parser.add_argument('--batch-size', type=int, default=32)
    parser.add_argument('--seed', type=int, default=42)
    parser.add_argument('--evaluate-ensemble', action='store_true',
                        help='Evaluate soft-voting on separate Test split (research only).')
    return parser.parse_args()


def get_generators(data_root: Path, batch_size: int, seed: int):
    required = ['Train', 'Val', 'Test']
    for split in required:
        if not (data_root / split).is_dir():
            raise FileNotFoundError(f'Missing dataset directory: {data_root / split}')
    augmentation = ImageDataGenerator(rescale=1 / 255.0, rotation_range=10,
                                       width_shift_range=0.1, height_shift_range=0.1,
                                       horizontal_flip=True)
    plain = ImageDataGenerator(rescale=1 / 255.0)
    opts = dict(target_size=(224, 224), batch_size=batch_size, class_mode='binary')
    train = augmentation.flow_from_directory(data_root / 'Train', shuffle=True,
                                              seed=seed, **opts)
    val = plain.flow_from_directory(data_root / 'Val', shuffle=False, **opts)
    test = plain.flow_from_directory(data_root / 'Test', shuffle=False, **opts)
    if len(train.class_indices) != 2 or not (train.class_indices == val.class_indices == test.class_indices):
        raise ValueError('Train/Val/Test must contain the same two class folders.')
    return train, val, test


def make_candidate(path: Path, learning_rate: float, dropout_rate: float) -> tf.keras.Model:
    # Fresh load per experiment: prevents accidental layer/weight sharing.
    model = tf.keras.models.load_model(path, compile=False)
    dropout_layers = [x for x in model.layers if isinstance(x, tf.keras.layers.Dropout)]
    if len(dropout_layers) != 2:
        raise ValueError(f'Expected two head Dropout layers; found {len(dropout_layers)}.')
    for layer in dropout_layers:
        layer.rate = dropout_rate
    # Keep the pretrained VGG19 backbone frozen, but train head Dense layers.
    # This is head retraining, not unfrozen VGG19 backbone fine-tuning.
    backbone = model.layers[0]
    if not isinstance(backbone, tf.keras.Model):
        raise ValueError('Expected nested VGG19 as the first stage-2 model layer.')
    backbone.trainable = False
    for layer in model.layers[1:]:
        layer.trainable = True
    model.compile(optimizer=tf.keras.optimizers.Adam(learning_rate=learning_rate),
                  loss='binary_crossentropy', metrics=['accuracy'])
    return model


def evaluate_ensemble(files: list[Path], generator) -> dict:
    """Average class-1 probabilities; stream models one by one to limit RAM.

    NOT a production selection criterion without independent evaluation.
    """
    total = None
    candidate_accuracy = []
    for file in files:
        tf.keras.backend.clear_session()
        model = tf.keras.models.load_model(file, compile=False)
        generator.reset()
        probabilities = model.predict(generator, verbose=0).reshape(-1)
        if len(probabilities) != len(generator.classes):
            raise RuntimeError('Model predictions and test labels have different lengths.')
        total = probabilities.astype(np.float64) if total is None else total + probabilities
        candidate_accuracy.append(float(np.mean((probabilities >= 0.5) == generator.classes)))
        del model
        gc.collect()
    ensemble_probs = total / len(files)
    return {
        'candidate_test_accuracy': candidate_accuracy,
        'ensemble_test_accuracy': float(np.mean((ensemble_probs >= 0.5) == generator.classes)),
        'method': 'arithmetic mean of nine class-1 probabilities; threshold 0.5',
        'warning': 'Experimental only. Not deployed to Android.'
    }


def main() -> None:
    args = get_args()
    if not args.base_model.is_file():
        raise FileNotFoundError(f'Stage-2 model is required: {args.base_model}')
    if args.epochs < 1 or args.batch_size < 1:
        raise ValueError('epochs and batch-size must be positive')
    args.output_dir.mkdir(parents=True, exist_ok=True)
    train, val, test = get_generators(args.data_root, args.batch_size, args.seed)
    report = {'origin': str(args.base_model), 'deployed': False,
              'reason': 'Model size / inference cost vs. mobile availability',
              'class_indices': train.class_indices, 'experiments': []}
    files = []
    trial_num = 0
    for learning_rate in LEARNING_RATES:
        for dropout_rate in DROPOUT_RATES:
            trial_num += 1
            tf.keras.backend.clear_session()
            tf.keras.utils.set_random_seed(args.seed)  # same initial weights + controlled RNG
            model = make_candidate(args.base_model, learning_rate, dropout_rate)
            target = args.output_dir / f'mpox_v3_candidate_{trial_num:02d}.keras'
            checkpoint = tf.keras.callbacks.ModelCheckpoint(
                str(target), monitor='val_accuracy', mode='max', save_best_only=True)
            history = model.fit(train, validation_data=val, epochs=args.epochs,
                                callbacks=[checkpoint], verbose=1)
            if not target.is_file():
                raise RuntimeError(f'No checkpoint saved: {target}')
            files.append(target)
            report['experiments'].append({
                'trial': trial_num, 'learning_rate': learning_rate,
                'dropout_rate': dropout_rate, 'epochs': args.epochs,
                'best_validation_accuracy': float(max(history.history['val_accuracy'])),
                'model_path': str(target), 'model_size_bytes': target.stat().st_size,
            })
            del model
            gc.collect()
    report['total_candidate_model_bytes'] = sum(p.stat().st_size for p in files)
    report['stage2_model_bytes'] = args.base_model.stat().st_size
    if args.evaluate_ensemble:
        # Include the actual deployment candidate in the offline comparison.
        tf.keras.backend.clear_session()
        baseline = tf.keras.models.load_model(args.base_model, compile=False)
        test.reset()
        baseline_probs = baseline.predict(test, verbose=0).reshape(-1)
        baseline_accuracy = float(np.mean((baseline_probs >= 0.5) == test.classes))
        del baseline
        gc.collect()
        report['test_evaluation'] = evaluate_ensemble(files, test)
        report['test_evaluation']['stage2_single_model_test_accuracy'] = baseline_accuracy
    (args.output_dir / 'experiments.json').write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print('9 candidates generated. These are experimental and are NOT Android deployment models.')


if __name__ == '__main__':
    main()
