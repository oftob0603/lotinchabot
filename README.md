# Kanal -> Izoh (comment) boti

Kanalga tashlangan postni (matn/rasm/video/albom) diskussiya guruhidagi
izohlarga krillcha matnda avtomatik joylashtiradi. Faqat `.env` dagi
`ADMIN_IDS` ro'yxatidagi foydalanuvchilar uchun ishlaydi.

## 1. GitHub'ga yuklash

```bash
git init
git add .
git commit -m "Kanal izoh boti"
git branch -M main
git remote add origin https://github.com/<username>/<repo>.git
git push -u origin main
```

**MUHIM:** `.env` faylini hech qachon GitHub'ga yuklamang — u
`.gitignore`da allaqachon berkitilgan. Faqat `.env.example` yuklanadi,
u shunchaki namuna.

## 2. Railway orqali deploy

1. https://railway.app -> **New Project** -> **Deploy from GitHub repo**
2. O'zingiz yuklagan repo'ni tanlang
3. Loyiha ochilgach, **Variables** bo'limiga o'ting va quyidagilarni
   qo'shing:
   - `BOT_TOKEN` = @BotFather'dan olingan token
   - `ADMIN_IDS` = o'z Telegram ID'ingiz (bir nechta bo'lsa vergul bilan:
     `111111111,222222222`)
4. Railway `Procfile`ni avtomatik tanib, `python channel_comment_bot.py`
   buyrug'i bilan botni ishga tushiradi (agar ishga tushmasa, **Settings
   -> Deploy -> Start Command** ga qo'lda `python channel_comment_bot.py`
   deb yozing).
5. **Deploy** tugmasini bosing.

## 4. Railway'da Volume ulash (majburiy — ma'lumotlar o'chib ketmasligi uchun)

`admins.json` va `allowed_chats.json` fayllari botning ishchi papkasida
saqlanadi. Railway'da konteyner qayta ishga tushganda (masalan yangi
deploy paytida) bu fayllar **yo'qolib qolishi mumkin**, agar Volume
ulanmagan bo'lsa. Shuning uchun quyidagini qiling:

1. Railway loyihangizda **servisni** oching (bot ishlayotgan servis).
2. **Settings** -> **Volumes** bo'limiga o'ting.
3. **+ New Volume** tugmasini bosing.
4. **Mount path** sifatida `/data` deb yozing (yoki xohlagan nom, lekin
   shu qo'llanmada `/data` deb olamiz).
5. Saqlang — Railway servisni avtomatik qayta deploy qiladi.
6. **Variables** bo'limiga qaytib, quyidagi ikkita o'zgaruvchini
   qo'shing (fayllarni shu doimiy diskka yozish uchun):
   - `ADMINS_FILE` = `/data/admins.json`
   - `ALLOWED_CHATS_FILE` = `/data/allowed_chats.json`
7. Qayta deploy bo'lishini kuting.

Shundan keyin `/add`, `/addadmin` kabi buyruqlar orqali qo'shilgan
ma'lumotlar Railway qayta ishga tushsa ham **o'chib ketmaydi**.

## 5. Botni sozlash

1. Botga `/start` yozing (agar ID'ingiz `ADMIN_IDS`da bo'lmasa, ruxsat
   berilmaydi — `/myid` orqali ID'ingizni bilib, uni Railway'dagi
   `ADMIN_IDS` o'zgaruvchisiga qo'shing va qayta deploy qiling).
2. Botni **kanalingizga** admin qilib qo'shing.
3. Kanalga **diskussiya guruhi** ulanganligiga ishonch hosil qiling
   (Kanal sozlamalari -> Discussion).
4. Botni **diskussiya guruhiga** ham admin qilib qo'shing.
5. **O'sha guruhda** `/add` deb yozing — shundagina bot o'sha guruhni
   "ruxsat berilgan" deb belgilaydi va izoh yozishni boshlaydi.
   `/add` yozilmagan guruhda bot hech narsa qilmaydi, hatto admin
   bo'lsa ham.

   Agar botni ADMIN_IDS'da bo'lmagan boshqa kishi biror kanal yoki
   guruhga qo'shsa, bot avtomatik o'sha yerdan chiqib ketadi.

Shundan so'ng kanalga tashlangan har bir post (rasm/video/albom/matn)
avtomatik ravishda krillcha matnda izohga joylanadi.

## Chatlarni boshqarish

- `/add` — joriy guruh/kanalni ruxsat berilganlar ro'yxatiga qo'shish
  (guruhning o'zida yozilishi kerak)
- `/removechat` — joriy chatni ruxsat ro'yxatidan olib tashlash
- `/chatid` — joriy chat ID'si va holatini ko'rish
- `/listchats` — ruxsat berilgan barcha chatlar ro'yxati

## Adminlarni boshqarish

- `/myid` — o'z Telegram ID'ingizni ko'rish
- `/addadmin <user_id>` — yangi admin qo'shish (faqat mavjud adminlar)
- `/removeadmin <user_id>` — adminni o'chirish
- `/listadmins` — joriy adminlar ro'yxati

Runtime'da qo'shilgan adminlar va ruxsat berilgan chatlar mos ravishda
`admins.json` va `allowed_chats.json` fayllarida (yoki Volume ulangan
bo'lsa, "4. Railway'da Volume ulash" bo'limida ko'rsatilgan `/data`
diskida) saqlanadi.
