# Panda Training Standalone

واجهة Windows مستقلة لإعداد الالتقاط، وفحص الأجهزة، وإدارة ملفات التدريب. لا يحتاج المستخدم النهائي إلى Python أو Gtuner.

## التشغيل

1. شغّل `PandaTrainingStandalone.exe`.
2. افتح **Diagnostics** وثبّت ViGEmBus إذا ظهر بحالة Missing. قد يتطلب Windows إعادة التشغيل.
3. صِل الكنترولر واختر ملفًا شخصيًا أو Preset.
4. اضغط **Start Engine**. إذا غاب الكنترولر أو فشل DXcam يبقى البرنامج مفتوحًا، وتظهر الحالة في Dashboard وDiagnostics.
5. HidHide اختياري؛ يمنع ظهور الكنترولر الفعلي والافتراضي كجهازين منفصلين في بعض البرامج.

الإعداد الافتراضي يمرر Left Stick دون تعديل. تصحيح الرؤية يضاف إلى Right Stick فقط حسب وضع التفعيل المحدد.

## الإعدادات والملفات الشخصية

- تحفظ تفضيلات التطبيق في `%APPDATA%\PandaTrainingStandalone\config.json`.
- تحفظ ملفات Screen وDetection وResponse في `%APPDATA%\PandaTrainingStandalone\profiles\`.
- تحفظ سجلات التشغيل في `%APPDATA%\PandaTrainingStandalone\logs\`.
- تحفظ الملفات بصيغة JSON باستخدام استبدال ذري.
- `Smooth` و`Balanced` و`Responsive` تغيّر فعليًا معاملات الاستجابة.
- يطبّق المحرك تغييرات الإعداد أثناء التشغيل دون إعادة تشغيله.

## المتطلبات والبناء

يتطلب البناء Python 3.12 على Windows. يستخدم التطبيق PySide6 للواجهة، وDXcam وNumPy وOpenCV للالتقاط والرؤية. يستدعي بناء Windows المستودع الرسمي لـ vgamepad ويضع ملف العميل `ViGEmClient.dll` محليًا؛ لا يشغّل `setup.py` ولا يثبت ViGEmBus أثناء CI.

```powershell
python -m pip install -r requirements.txt
./build_windows.ps1
```

GitHub Actions يبني ملفًا واحدًا windowed باسم `PandaTrainingStandalone.exe`، ويحسب SHA256 ويرفع الملفين كـ artifact. البناء مضبوط على `windows-latest` وPython 3.12.

## فحوصات محلية

```powershell
python -m compileall -q panda tests main.py app.py
python -m unittest discover -s tests -v
```

يجب بناء EXE على Windows لأن DXcam وViGEmBus وملف vgamepad المضمّن خاصة بويندوز.
