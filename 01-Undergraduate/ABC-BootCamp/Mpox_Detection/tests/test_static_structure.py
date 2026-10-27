"""Static integration checks only: requires no TensorFlow or Android SDK."""
import ast
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class ModelPackagingChecks(unittest.TestCase):
    def test_all_four_sources_parse(self):
        for name in ('Mpox_classification_v1.py', 'Mpox_classification_v2.py',
                     'Mpox_classification_v3.py', 'Model_Lightweighting.py'):
            with self.subTest(file=name):
                ast.parse((ROOT / name).read_text(encoding='utf-8'))

    def test_v3_loads_selected_v2(self):
        s = (ROOT / 'Mpox_classification_v3.py').read_text(encoding='utf-8')
        self.assertIn('models/monkeypox_classification_model2.keras', s)
        self.assertNotIn("load_model('monkeypox_classification_model.keras')", s)

    def test_v3_no_layer_sharing(self):
        s = (ROOT / 'Mpox_classification_v3.py').read_text(encoding='utf-8')
        self.assertIn('tf.keras.models.load_model(path, compile=False)', s)
        self.assertIn('LEARNING_RATES', s)
        self.assertIn('DROPOUT_RATES', s)

    def test_checkpoint_in_fit(self):
        for name in ('Mpox_classification_v1.py', 'Mpox_classification_v2.py'):
            with self.subTest(file=name):
                s = (ROOT / name).read_text(encoding='utf-8')
                self.assertIn('callbacks=[checkpoint]', s)
                self.assertNotIn('steps_per_epoch=train_generator.samples //', s)

    def test_converter_has_quantization_and_no_reinitialize(self):
        s = (ROOT / 'Model_Lightweighting.py').read_text(encoding='utf-8')
        self.assertIn('tf.lite.Optimize.DEFAULT', s)
        self.assertNotIn('layer.__init__(**config)', s)
        self.assertIn('inspect_mobile_io', s)

    def test_android_single_inference(self):
        s = (ROOT / 'Android-App/app/src/main/java/com/example/mpox_detection_submit/MainActivity.kt').read_text()
        self.assertEqual(s.count('interpreter.run(inputBuffer, output)'), 1)
        self.assertNotIn('predictions.count', s)
        self.assertIn('mpoxClassIndex', s)

    def test_readme_decision(self):
        s = (ROOT / 'README.md').read_text(encoding='utf-8')
        for value in ('132,018,708', '3차', '2차', '모바일', 'diagrams/model-selection.svg'):
            with self.subTest(value=value):
                self.assertIn(value, s)


if __name__ == '__main__':
    unittest.main()
