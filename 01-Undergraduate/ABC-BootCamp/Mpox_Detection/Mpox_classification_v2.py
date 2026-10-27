"""Stage 2: VGG19 feature extraction + binary classification head.

This is the selected deployment model. Preserve legacy RGB/255 preprocessing,
since the Android prototype also used RGB/255. Changing to VGG19's official
preprocess_input requires retraining and changing the Android preprocessing.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import tensorflow as tf
from tensorflow.keras import layers, models
from tensorflow.keras.applications import VGG19
from tensorflow.keras.callbacks import ModelCheckpoint
from tensorflow.keras.preprocessing.image import ImageDataGenerator


def get_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description='Stage 2 - frozen VGG19 feature extractor')
    parser.add_argument('--data-root', type=Path, default=Path('Mpox/Fold1/Fold1/Fold1'))
    parser.add_argument('--output', type=Path, default=Path('models/monkeypox_classification_model2.keras'))
    parser.add_argument('--epochs', type=int, default=100)
    parser.add_argument('--batch-size', type=int, default=32)
    parser.add_argument('--seed', type=int, default=42)
    parser.add_argument('--augmentation', choices=['legacy', 'moderate'], default='legacy')
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
    backbone = VGG19(weights='imagenet', include_top=False, input_shape=(224, 224, 3))
    backbone.trainable = False
    model = models.Sequential([
        backbone,
        layers.Flatten(),
        layers.Dense(512, activation='relu'),
        layers.Dropout(0.5),
        layers.Dense(256, activation='relu'),
        layers.Dropout(0.3),
        layers.Dense(1, activation='sigmoid'),
    ])
    model.compile(loss='binary_crossentropy',
                  optimizer=tf.keras.optimizers.Adam(learning_rate=1e-5),
                  metrics=['accuracy'])
    return model


def main() -> None:
    args = get_args()
    if args.epochs < 1 or args.batch_size < 1:
        raise ValueError('--epochs and --batch-size must be positive.')
    tf.keras.utils.set_random_seed(args.seed)
    train, val, test = make_generators(args.data_root, args.batch_size,
                                       args.seed, args.augmentation)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    checkpoint = ModelCheckpoint(str(args.output), monitor='val_accuracy',
                                 save_best_only=True, mode='max', verbose=1)
    model = build_model()
    model.fit(train, epochs=args.epochs, validation_data=val, callbacks=[checkpoint])
    best = tf.keras.models.load_model(args.output)
    test_loss, test_accuracy = best.evaluate(test, verbose=1)
    metadata = {
        'stage': 'v2-vgg19-selected-for-android',
        'test_loss': float(test_loss), 'test_accuracy': float(test_accuracy),
        'class_indices': train.class_indices, 'image_size': [224, 224],
        'normalization': 'RGB divided by 255', 'augmentation': args.augmentation,
        'model_bytes': args.output.stat().st_size,
        'note': 'New execution results; not the historical 88% record.'
    }
    args.output.with_suffix('.metadata.json').write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2), encoding='utf-8')
    print(f'Selected model: {args.output}\nTest accuracy: {test_accuracy:.4f}')
    print('Check *.metadata.json class_indices before mapping output to Mpox on Android.')


if __name__ == '__main__':
    main()
