# Jhumong Digital Hub
Android app + Colab backend (libre). Si JARVIS ang utak: nag-uusap, gumagawa at nag-eedit ng video.

1. APP: i-upload ang laman ng folder na ito sa GitHub repo (palitan ang luma). Sa tab na Actions
   > Build APK, hintayin matapos, i-download ang artifact `JhumongDigitalHub-apk`, i-install.
2. BACKEND: buksan ang backend/jarvis_backend.py sa Google Colab (T4 GPU). Cell 1:
   !pip -q install diffusers transformers accelerate flask flask-cors opencv-python-headless
   Cell 2: i-paste ang file at i-run. Kopyahin ang https://...trycloudflare.com sa app.
3. Gamitin: "Gumawa ka ng kuwento ng ..., 4 na eksena" / "i-upscale mo" / "lagyan ng caption ..."
   Pindutin ang 💾 para i-save sa Gallery, tapos i-upload sa Reels/Shorts.
