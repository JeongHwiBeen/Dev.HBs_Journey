"""Stage 1: train a scratch CNN baseline for binary Mpox image classification.

The original project documented ~79% as its best result; running this revised
script is a NEW experiment and does not reproduce that figure automatically.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import tensorflow as tf
from tensorflow.keras import layers, models
from tensorflow.keras.callbacks import ModelCheckpoint
from tensorflow.keras.preprocessing.image import ImageDataGenerator

DATA_ROOT = Path('Mpox/Fold1/Fold1/Fold1')


def get_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description='Stage 1 - scratch CNN')
    parser.add_argument('--data-root', type=Path, default=DATA_ROOT)
    parser.add_argument('--output', type=Path, default=Path('models/monkeypox_classification_model.keras'))
    parser.add_argument('--epochs', type=int, default=200)
    parser.add_argument('--batch-size', type=int, default=32)
    parser.add_argument('--seed', type=int, default=42)
    parser.add_argument('--augmentation', choices=['legacy', 'moderate'], default='legacy',
                        help='legacy: original aggressive augmentation; moderate: reduced transforms')
    return parser.parse_args()


def make_generators(root: Path, batch_size: int, seed: int, augmentation: str):
    paths = {split: root / split for split in ('Train', 'Val', 'Test')}
    for name, folder in paths.items():
        if not folder.is_dir():
            raise FileNotFoundError(f'Missing {name} directory: {folder}')

    augment = (dict(rotation_range=180, width_shift_range=0.5,
                    height_shift_range=0.5, shear_range=0.5, zoom_range=0.5,
                    horizontal_flip=True, vertical_flip=True, fill_mode='nearest')
               if augmentation == 'legacy' else
               dict(rotation_range=15, width_shift_range=0.1,
                    height_shift_range=0.1, zoom_range=0.1,
                    horizontal_flip=True, fill_mode='nearest'))
    train_aug = ImageDataGenerator(rescale=1.0 / 255.0, **augment)
    eval_aug = ImageDataGenerator(rescale=1.0 / 255.0)
    options = dict(target_size=(224, 224), batch_size=batch_size, class_mode='binary')
    train = train_aug.flow_from_directory(paths['Train'], shuffle=True, seed=seed, **options)
    val = eval_aug.flow_from_directory(paths['Val'], shuffle=False, **options)
    test = eval_aug.flow_from_directory(paths['Test'], shuffle=False, **options)
    if len(train.class_indices) != 2:
        raise ValueError(f'Expected exactly two classes, got {train.class_indices}')
    if train.class_indices != val.class_indices or train.class_indices != test.class_indices:
        raise ValueError('Class folder names/order differ between Train, Val and Test.')
    return train, val, test


def build_model() -> tf.keras.Model:
    model = models.Sequential([
        layers.Input(shape=(224, 224, 3)),
        layers.Conv2D(32, (3, 3), activation='relu'),
        layers.MaxPooling2D((2, 2)),
        layers.Conv2D(64, (3, 3), activation='relu'),
        layers.MaxPooling2D((2, 2)),
        layers.Flatten(),
        layers.Dense(512, activation='relu'),
        layers.Dropout(0.5),
        layers.Dense(256, activation='relu'),
        layers.Dropout(0.3),
        layers.Dense(1, activation='sigmoid'),
    ])
    model.compile(optimizer=tf.keras.optimizers.Adam(),
                  loss='binary_crossentropy', metrics=['accuracy'])
    return model


def main() -> None:
    args = get_args()
    if args.epochs < 1 or args.batch_size < 1:
        raise ValueError('--epochs and --batch-size must be positive.')
    tf.keras.utils.set_random_seed(args.seed)
    train, val, test = make_generators(args.data_root, args.batch_size,
                                       args.seed, args.augmentation)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    model = build_model()
    # Unlike the original v1 script, this callback is ACTUALLY passed to fit.
    checkpoint = ModelCheckpoint(str(args.output), monitor='val_accuracy',
                                 save_best_only=True, mode='max', verbose=1)
    model.fit(train, epochs=args.epochs, validation_data=val, callbacks=[checkpoint])
    # Evaluate the best validation checkpoint, not the last epoch's weights.
    best = tf.keras.models.load_model(args.output)
    test_loss, test_accuracy = best.evaluate(test, verbose=1)
    metadata = {
        'stage': 'v1-scratch-cnn', 'test_loss': float(test_loss),
        'test_accuracy': float(test_accuracy), 'class_indices': train.class_indices,
        'image_size': [224, 224], 'normalization': 'RGB divided by 255',
        'augmentation': args.augmentation,
        'note': 'New execution results; not the historical 79% record.'
    }
    args.output.with_suffix('.metadata.json').write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2), encoding='utf-8')
    print(f'Best checkpoint: {args.output}\nTest accuracy: {test_accuracy:.4f}')


if __name__ == '__main__':
    main()
