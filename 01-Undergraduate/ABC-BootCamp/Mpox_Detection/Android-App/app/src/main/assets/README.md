# Model asset instructions

Place the **verified** stage-2 `model_v2.tflite` here before building.

The existing uploaded Android ZIP contained a 132,018,708-byte model. It is intentionally
excluded from this GitHub-ready source archive because of GitHub's normal 100MB file limit.
Use Git LFS or a release artifact if distributing it. Never substitute a v3 ensemble.

`MainActivity.kt` expects FLOAT32 `[1,224,224,3]` RGB values scaled to [0,1],
FLOAT32 `[1,1]` sigmoid output, and assumes class index 1 = Mpox. Verify the
last assumption with the v2 metadata/class folder names before publishing.
