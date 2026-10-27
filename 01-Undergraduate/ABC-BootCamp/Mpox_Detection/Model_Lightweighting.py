"""Convert selected stage-2 Keras model to Android-compatible TFLite.

Default dynamic-range quantization attempts actual weight compression while
retaining FLOAT32 input/output. Conversion alone ('none') is NOT quantization.
Test new artifacts on the actual Android TFLite runtime before replacing assets.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import tensorflow as tf


def get_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description='Convert selected v2 model to TFLite')
    p.add_argument('--model', type=Path,
                   default=Path('models/monkeypox_classification_model2.keras'))
    p.add_argument('--output', type=Path, default=Path('artifacts/model_v2.tflite'))
    p.add_argument('--quantization', choices=['none', 'dynamic', 'float16'], default='dynamic')
    p.add_argument('--verify-parity', action='store_true',
                   help='Run synthetic-image Keras vs TFLite output comparison.')
    return p.parse_args()


def convert(model: tf.keras.Model, mode: str) -> bytes:
    # No in-place layer.__init__() calls: re-initializing existing layers can
    # invalidate loaded weights, and is unnecessary for ordinary conversion.
    converter = tf.lite.TFLiteConverter.from_keras_model(model)
    if mode in {'dynamic', 'float16'}:
        converter.optimizations = [tf.lite.Optimize.DEFAULT]
    if mode == 'float16':
        converter.target_spec.supported_types = [tf.float16]
    return converter.convert()


def inspect_mobile_io(tflite_path: Path) -> dict:
    """Always validate Android's expected float32 shape/dtype interface."""
    interpreter = tf.lite.Interpreter(model_path=str(tflite_path))
    interpreter.allocate_tensors()
    inputs, outputs = interpreter.get_input_details(), interpreter.get_output_details()
    if len(inputs) != 1 or len(outputs) != 1:
        raise RuntimeError('Android prototype expects exactly one input and output tensor.')
    if list(inputs[0]['shape']) != [1, 224, 224, 3] or list(outputs[0]['shape']) != [1, 1]:
        raise RuntimeError(f'Unexpected TFLite IO shape: {inputs[0]["shape"]}, {outputs[0]["shape"]}')
    if inputs[0]['dtype'] != np.float32 or outputs[0]['dtype'] != np.float32:
        raise RuntimeError('Android prototype expects float32 IO; revise Android code if model differs.')
    return {'input_shape': [int(n) for n in inputs[0]['shape']],
            'output_shape': [int(n) for n in outputs[0]['shape']],
            'input_dtype': str(inputs[0]['dtype']), 'output_dtype': str(outputs[0]['dtype'])}


def check_parity(model: tf.keras.Model, tflite_path: Path) -> dict:
    """Sanity-check numeric conversion, not clinical accuracy or generalization."""
    # 224x224 RGB, normalized to [0,1], matching the Android code.
    rng = np.random.default_rng(42)
    x = rng.random((1, 224, 224, 3), dtype=np.float32)
    keras_out = model(x, training=False).numpy()
    interpreter = tf.lite.Interpreter(model_path=str(tflite_path))
    interpreter.allocate_tensors()
    inputs = interpreter.get_input_details()
    outputs = interpreter.get_output_details()
    if len(inputs) != 1 or len(outputs) != 1:
        raise RuntimeError('Android prototype expects exactly one input and output tensor.')
    if list(inputs[0]['shape']) != [1, 224, 224, 3] or list(outputs[0]['shape']) != [1, 1]:
        raise RuntimeError(f'Unexpected TFLite IO shape: {inputs[0]["shape"]}, {outputs[0]["shape"]}')
    if inputs[0]['dtype'] != np.float32 or outputs[0]['dtype'] != np.float32:
        raise RuntimeError('Android prototype uses FLOAT32 input/output; quantized tensors need app changes.')
    interpreter.set_tensor(inputs[0]['index'], x)
    interpreter.invoke()
    tflite_out = interpreter.get_tensor(outputs[0]['index'])
    return {'max_absolute_difference_synthetic': float(np.max(np.abs(keras_out - tflite_out))),
            'keras_output_synthetic': keras_out.tolist(),
            'tflite_output_synthetic': tflite_out.tolist(),
            'input_shape': [int(n) for n in inputs[0]['shape']],
            'output_shape': [int(n) for n in outputs[0]['shape']],
            'input_dtype': str(inputs[0]['dtype']), 'output_dtype': str(outputs[0]['dtype'])}


def main() -> None:
    args = get_args()
    if not args.model.is_file():
        raise FileNotFoundError(f'Missing selected stage-2 model: {args.model}')
    args.output.parent.mkdir(parents=True, exist_ok=True)
    model = tf.keras.models.load_model(args.model, compile=False)
    tflite_data = convert(model, args.quantization)
    args.output.write_bytes(tflite_data)
    io_info = inspect_mobile_io(args.output)
    report = {
        'source_model': str(args.model),
        'deployment_stage': 'v2 (VGG19) single model, NOT v3 ensemble',
        'mobile_io': io_info,
        'conversion_mode': args.quantization,
        'keras_file_bytes': args.model.stat().st_size,
        'tflite_file_bytes': args.output.stat().st_size,
        'tflite_vs_keras_file_ratio': round(args.output.stat().st_size / args.model.stat().st_size, 5),
        'warning': 'File format/quantization and size alone do not prove accuracy or speed. Test on phone.',
    }
    if args.verify_parity:
        report['synthetic_parity'] = check_parity(model, args.output)
    report_path = args.output.with_suffix('.report.json')
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(f'Wrote {args.output} ({args.output.stat().st_size:,} bytes)')
    print(f'Report: {report_path}')
    print('Check the Android class-label mapping and device compatibility before release.')


if __name__ == '__main__':
    main()
