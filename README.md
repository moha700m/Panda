# Panda Training Standalone

نسخة Windows مستقلة للتدريب/الأوفلاين. لا تحتاج Python أو Gtuner للمستخدم النهائي.

## الاستخدام
1. شغّل `PandaTrainingStandalone.exe`.
2. إذا كان ViGEmBus مفقودًا اضغط `Install / Repair drivers` ووافق على UAC.
3. HidHide اختياري لكنه موصى به لمنع ظهور الكنترولر الحقيقي والافتراضي معًا.
4. اضغط START.
5. البرنامج يمرر الكنترولر كما هو، ويضيف تصحيح الشاشة إلى Right Stick فقط أثناء ADS.
6. Left Stick يمر كما هو بدون تعديل من محرك الرؤية.

## البناء
GitHub Actions يبني نسخة Windows تلقائيًا من:
`.github/workflows/build-windows.yml`

الناتج:
`PandaTrainingStandalone.exe` + `SHA256.txt`
