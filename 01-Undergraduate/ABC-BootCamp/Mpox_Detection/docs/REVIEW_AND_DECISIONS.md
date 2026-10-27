# Code review and design decisions

## Project decision, not a failed experiment

1. Baseline scratch CNN (stage 1) → VGG19 (stage 2) → 9-candidate experiment (stage 3).
2. Mobile deployment favored **one stage-2 VGG19** over a multi-model ensemble.
3. A higher-performing ensemble is *possible*, not guaranteed; there are no historical ensemble accuracy measurements in the four submitted scripts.
4. The original Android asset `model_v2.tflite` is **132,018,708 bytes (~125.90 MiB)**. Its actual compression ratio cannot be stated without the source `.keras` size. The original `Model_Lightweighting.py` only converted file formats; there was **no quantization**.
5. The patched converter adds quantization options, but they have not been executed here. Mobile compatibility with the app's TFLite 2.10 runtime is not yet verified.

## Original code defects corrected

| File | Original issue | Revision |
| --- | --- | --- |
| v1 | Defined `ModelCheckpoint` but never passed to `fit` | Added actual `callbacks=[checkpoint]` |
| v1 & v2 | `steps_per_epoch=dataset.samples//200` and `validation_steps=...//100` ignored many batches; may produce zero steps | Let `fit` iterate all generated batches |
| v1 & v2 | Last-epoch `model.save()` overwrote previous best checkpoint | Load and evaluate best saved checkpoint |
| v1 & v2 | Only simple final metric output; class-to-sigmoid mapping undocumented | Save `*.metadata.json` with class indices and test metrics |
| v3 | `load_model('monkeypox_classification_model.keras')` loaded **v1**, inconsistent with comments | Explicitly load selected **v2** |
| v3 | Nine candidate graphs reused the same `base_model` layers | Load a fresh model per combination |
| v3 | New Dropout inserted near output but potential unintentional shared backbone; inconsistent claim of VGG19 fine tuning | Modify 2 existing head Dropout rates and train head, freeze VGG19 |
| v3 | No actual ensemble prediction | Optional offline soft-voting evaluation; not used by Android |
| converter | Invoked `layer.__init__(**config)` on already loaded layers | Remove unsafe re-initialization |
| converter | No actual compression optimization | Offer `dynamic` and `float16` TFLite converter modes and size report |
| Android | Same interpreter, same input buffer used three times then majority voted | Single inference; no pseudo-ensemble |
| Android | `uploadedImageView` was `GONE` after setting bitmap | Show ImageView when image selected/captured |
| Android | Camera permission grant didn't start preview immediately | Implement camera startup in permission callback |
| Android | Duplicate TFLite dependency 2.9.0 and 2.10.0 | Retain 2.10.0 only |
| Android | Exposed guidance Activity and statement falsely asserting diagnosis | Set exported=false, fix guidance wording |

## Important limitations / validation checklist

- The recorded accuracy figures (79% and 88%) came from original *comments*, not supplied experiment logs.
- TensorFlow and original data/model weights are absent from the runtime; **Python was syntax-checked only**. No claim of re-training or converged accuracy.
- Android Studio build and on-device runtime were **not executed** here.
- VGG19 historically used RGB/255 despite official `preprocess_input` expecting a different transform. Changing preprocessing requires retraining AND matching Android.
- `ImageDataGenerator.flow_from_directory` assigns class indices alphabetically. **Check `*.metadata.json`** and change `mpoxClassIndex` in Android if positive class has index 0. The previous app assumed class 1 = Mpox.
- The float32 `[1,224,224,3]` input and `[1,1]` output is the expected interface from the submitted Python and Kotlin code; validate the actual `.tflite` tensor metadata on a device.
- Heavy augmentation from v1/v2 is preserved under `--augmentation legacy` for experimental fidelity; `--augmentation moderate` is available for fresh experiments. Results may change.
- Real quality assessment should include sensitivity/recall, specificity, F1, confusion matrix, threshold calibration, split leakage audit, dataset demographic representativeness, and model size/latency measurements on target devices.
- Even a correctly classified skin photograph **cannot diagnose Mpox**.
- Android app model is excluded because it exceeds typical GitHub 100 MB size limit. Fetch it from the submitted Application ZIP or publish via Git LFS/Release if rights allow.
- The installed old Android runtime (TFLite 2.10.0) may not support an artifact produced by a newer converter. Test in emulator/physical device; align versions only after validating.
- Camera-captured JPEG orientation is not normalized using EXIF in the original app; adjust if testing confirms rotated images.
