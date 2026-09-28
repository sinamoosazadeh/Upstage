# VERIFY_V1c — راستی‌آزمایی مستقل ممیزی APEX_GEN5 (نشست V1c: حلقهٔ اجرا — bootstrap, repair, bridge, supervision)

- **مبنای کد:** کامیت `85b2c155d7b054a468379ddfd802eb239d0801f9` (تأییدشده با `git rev-parse HEAD` و `git log -1`؛ شاخهٔ `arena/01a0e9af-upstage`).
- **ورودی ممیزی:** `AUDIT/APEX_GEN5_AUDIT.md` (کامیت `015d19bd…`) و `AUDIT/APEX_GEN5_AUDIT_INDEX.md` (کامیت `690e2d88…`)، دریافت‌شده با `git fetch origin 690e2d8899319a7c7a96456f92c3008878e59346`.
- **دامنهٔ نشست (۹ ردیف، همه الزامی):** C-001، C-005، C-007، C-009، C-011، C-014، C-015، O-006، V-003.
- **زمینهٔ متقابل:** C-002 در نشست V1a با حکم «تأیید S0» به‌عنوان ریشهٔ کدی ISSUE-075 ثبت شده است (شاخهٔ `arena/01a0e911-upstage`، فایل `AUDIT/VERIFY_V1a.md`)؛ در این نشست به آن استناد می‌شود و بازبینی نمی‌شود.
- **روش:** خواندن کامل فایل‌ها و فراخوانندگان مستقیم، نقل بند قرارداد/تصمیم، بازتولید با pytest یا probe (در `AUDIT/probes_V1c/`)، EXPLAIN QUERY PLAN روی DDL واقعی در صورت پرس‌وجوی SQLite. همهٔ probeها بدون شبکه، بدون راز/.env و بدون تغییر کد مخزن اجرا شده‌اند.
- **مرز شواهد:** موفقیت fixture/دادهٔ مصنوعی در این سند معادل تأیید روی دستگاه واقعی نیست و هرجا صحت وابسته به دادهٔ واقعی است، صریحاً با حکم «نیازمند شاهد از دستگاه» مشخص شده است.

## جدول خلاصه

| شناسه | حکم | شدت ممیز | شدت مستقل | فریز؟ | ارجاع متقابل (D/ISSUE) | گزینهٔ پیشنهادی |
|---|---|---|---|---|---|---|
| C-001 | تأیید | S3 | S3 | نه (scripts/run_apex.py فریز نیست) | H-008، K-026 | الف: انتقال ساخت Config به داخل try |
| C-005 | _در حال بررسی_ | S2 | — | — | C-015, D50 | — |
| C-007 | _در حال بررسی_ | S2 | — | — | — | — |
| C-009 | _در حال بررسی_ | S1 | — | — | — | — |
| C-011 | _در حال بررسی_ | S2 | — | — | K-020 | — |
| C-014 | _در حال بررسی_ | S2 | — | — | G-005، K-020 | — |
| C-015 | _در حال بررسی_ | S2 | — | — | C-005, D51 | — |
| O-006 | _در حال بررسی_ | S4 | — | — | — | — |
| V-003 | _در حال بررسی_ | S4 | — | — | D-001، D-002، E-016، H-007 | — |

## بخش‌های تفصیلی

_(پس از راستی‌آزمایی هر ردیف، بخش دوازده‌سرفصلهٔ آن در اینجا افزوده می‌شود.)_

### C-001 — ساخت Config بیرون handler خطای CLI

**ادعای ممیز (نقل کوتاه):** «`Config(args.env_file)` پیش از `try` اجرا می‌شود؛ خطای parser، permission یا decoding از خروجی کنترل‌شدهٔ CLI عبور نمی‌کند … traceback و گزارش ناهماهنگ به‌جای refusal قابل تشخیص» (`scripts/run_apex.py:1131–1133,1163–1168`؛ شدت S3).

**آنچه خواندم:**
- `scripts/run_apex.py:1–1173` (فایل کامل). در `main` خط 1131 `args = parser.parse_args(argv)`، خط 1132 `cfg = Config(args.env_file)` و خط 1133 `try:` است؛ یعنی ساخت Config یک خط پیش از مرز مدیریت خطاست. handlerهای خطا در خطوط 1167–1172 (`except KeyboardInterrupt`، `except AdapterError`، `except Exception as exc: _say(f"ERROR {type(exc).__name__}: {exc}"); return EXIT_ERROR`).
- `apex/config.py:1–512` (فایل کامل). `Config.__init__` (خط 139–140) فقط `self._env = _load_env(env_path)` را صدا می‌زند. `_load_env` (خط 124–136) با `os.path.exists(path)` از فایل ناشناخته محافظت می‌کند، اما وقتی فایل موجود است `parse_dotenv` (خط 93–121) آن را با `open(path, "r", encoding="utf-8")` می‌خواند و در سه حالت exception می‌دهد: خط بدون `=` → `ValueError("malformed .env line …")` (خط 106–108)؛ نام نام known → `ValueError("unknown runtime env name …")` (خط 114–117)؛ بایت غیرUTF-8 → `UnicodeDecodeError` از iteration روی handle. permission denied نیز از `open` به‌صورت `PermissionError` بالا می‌آید.
- فراخوانندگان: تنها سازندهٔ Config در مسیر CLI همین `main` است (`grep -rn "Config(" scripts/run_apex.py` → فقط خط 1132؛ ۶۴ مکان در کل مخزن `apex.config` را import می‌کنند که عمدتاً تست‌ها و wiring هستند، نه entry point دیگر). `parse_args` نیز بیرون try است اما خطاهای argparse با کد خروج ۲ و usage استاندارد خارج می‌شوند (رفتار عادی CLI).
- قرارداد: docstring بالای `run_apex.py` (خط 51–52): «Exit codes: 0 = READY, 2 = DEGRADED / refused, 3 = RECOVERY_REQUIRED, 1 = unexpected error (fail-closed, never a silent success)». در `APEX_GEN5.md` کلمهٔ کلیدی «fail-closed» (مثلاً خط 332: «fail-closed semantics everywhere (an undecidable or unhealthy state refuses to trade)») دربارهٔ رفتار معاملاتی است نه قالب پیام CLI؛ بندی که قالب خروجی خطای CLI را الزام کند پیدا نکردم. `PHASE2_DECISION_LOG.md` نیز دربارهٔ مرز خطای `main` تصمیمی ندارد (جست‌وجوی run_apex/composition root فقط ISSUE-CP9-006 را دربارهٔ plan bridge نشان داد).

**بازتولید:**
- دستور: `python3 AUDIT/probes_V1c/C-001.py` (فایل کامل در مخزن؛ خروجی خام در `AUDIT/probes_V1c/C-001.out`). پنج سناریو با subprocess روی CLI واقعی، بدون شبکه، بدون `.env` در ریشهٔ مخزن (تأیید: `ls -la .env` → هیچ)، با `APEX_DOTENV_PATH` پاک‌شده از env.
- نتایج واقعی (همه با `.env` مصنوعی در `/tmp`):
  - `.env` ناسالم (`THIS IS NOT A KEY VALUE LINE`): `exit_code=1` و **traceback خام** روی stderr (`ValueError: malformed .env line 1: expected NAME=VALUE` از `apex/config.py:105`) و **stdout کاملاً خالی** — حتی بنر boot چاپ نشد.
  - نام نام known در `.env` (`NOT_A_KNOWN_NAME=1`): `exit_code=1` با traceback خام `ValueError: unknown runtime env name …`.
  - `.env` غیرUTF-8 (`\xff\xfe…`): `exit_code=1` با traceback خام `UnicodeDecodeError: 'utf-8' codec can't decode byte 0xff`.
  - کنترل (خطای داخل try): `bootstrap --cells bogus` → `exit_code=1` و خط تمیز `ERROR ValueError: --cells expects SYMBOL:TIMEFRAME, got 'bogus'` روی stdout، بدون traceback.
  - `--env-file` به فایل ناموجود: به‌لطف نگهبان `os.path.exists` بدون خطا عبور کرد (exit 2 به‌خاطر وضعیت bootstrap، نه مرتبط با این ردیف).

**حکم و دلیل:** **تأیید**. تکها مسیر خروج Config (ValueError از parser، UnicodeDecodeError، PermissionError بالقوه) پیش از `try` رخ می‌دهد و خروجی، traceback خام است نه سطر کنترل‌شدهٔ `ERROR …`؛ درحالی‌که خطای معادل داخل try (`--cells`) سطر تمیز می‌دهد. نکتهٔ مهم خودِ ممیز نیز درست است: این «bypass یا ادامهٔ اجرا پس از خطا نیست» — کد خروج در هر دو حالت ۱ است و fail-closed بودن حفظ می‌شود؛ تنها **قالب و مبدأ گزارش** ناهماهنگ است. شدت مستقل = S3 (سندی/بهره‌برداری)، هم‌تراز با ممیز، چون اثر امنیتی/مالی ندارد و کد خروج درست می‌ماند.

**علت ریشه‌ای:** ترتیب دستورها در `main`: ساخت Config (که می‌تواند I/O و parse انجام دهد) بیرون از مرز `try/except` قرار گرفته، درحالی‌که docstring همان فایل وعدهٔ «fail-closed» با خروجی کنترل‌شده را می‌دهد. `_load_env` عمداً fail-closed طراحی شده (هر ناهنجاری در `.env` → exception) اما entry point آن exception را به قالب CLI ترجمه نمی‌کند.

**اثر مستقیم:** در صورت `.env` خراب/غیرUTF-8/خوانا‌نبودن: (الف) روی stderr traceback پایتون با مسیرهای داخلی فایل (`/home/user/Upstage/apex/config.py`…) دیده می‌شود؛ (ب) stdout هیچ نشانهٔ «ERROR»/«REFUSED» ندارد؛ (پ) کد خروج همچنان ۱ است (درست)، پس supervisorهایی که فقط کد را می‌سنجند متاثر نمی‌شوند، اما اسکریپت/اپراتوری که سطر `ERROR …` یا ساختار `REFUSED <code>` را انتظار دارد، گزارش ناسازگار می‌گیرد.

**اثرات ثانویه و تعاملات (بالادست/پایین‌دست):**
- بالادست: فقط `--env-file`/`APEX_DOTENV_PATH`/`.env` پیش‌فرض؛ راز واقعی لازم نیست (probe با فایل‌های مصنوعی انجام شد). نکتهٔ امنیتی: پاسخ traceback مسیر فایل و شمارهٔ خط را لو می‌دهد اما مقدار راز را هرگز چاپ نمی‌کند (`parse_dotenv` کل خط را در پیام نمی‌آورد؛ فقط شمارهٔ خط و نام کلید).
- پایین‌دست: هیچ تصمیم/ریسک/سفارش/دفترکلی درگیر نیست چون خطا پیش از start شدن هر سرویسی رخ می‌دهد و فرایند با ۱ می‌میرد. watchdog (`apex/ops/watchdog.py`) و gateway هنوز ساخته نشده‌اند. تنها تشخیص خطای اپراتور در اسکریپت اجرا و پشتیبانی دشوارتر می‌شود.
- تعامل با ردیف‌های دیگر: مستقل است؛ با H-008/K-026 (آموزش/OI) تنها هم‌محلی فایل دارد، اثر علی ندارد.

**نسبت با قرارداد و تصمیم‌ها:** هیچ بند normative در `APEX_GEN5.md` که قالب پیام خطای CLI را مقررداشت کند پیدا نشد؛ docstring `run_apex.py` (خط 51–52) تنها مرجع است و با رفتار فعلی **از نظر کد خروج** سازگار، **از نظر قالب خروجی** ناسازگار است. تصمیم مؤخری در DECISION_LOG که این رفتار را مصوب کند وجود ندارد.

**فریز و راه‌حل بیرون از فریز:** `scripts/run_apex.py` و `apex/config.py` در فهرست فریز (موتورها، data_catalog، research/bootstrap.py، backtest.py، شش YAML، requirements.lock) **نیستند**؛ اصلاح بدون حکم مالک ممکن است. نیازی به راه‌حل غیرمستقیم نیست.

**گزینه‌های اصلاح:**
- الف) انتقال `cfg = Config(args.env_file)` به داخل `try` (و در صورت لزوم تحویل `cfg=None` به مسیرها). اثر جانبی: همان کد خروج ۱، قالب خروجی به `ERROR ValueError: …` تبدیل می‌شود؛ هیچ آزمونی که traceback را pattern-match کند در repo دیده نمی‌شود (جست‌وجوی تست‌ها: تست‌های config مستقیماً `Config` را صدا می‌زنند نه از طریق CLI)؛ بدون مهاجرت DB، بدون تغییر هش/هویت.
- ب) نگه‌داشتن Config بیرون ولی قراردادن `try/except (ValueError, OSError, UnicodeError)` اختصاصی دور آن که `ERROR …` چاپ و `EXIT_ERROR` برگرداند. اثر جانبی: دقیق‌تر (فقط خطاهای شناخته‌شده قالب‌بندی می‌شوند و bugهای programmatique همچنان traceback می‌مانند — که مزیت تشخیصی است)؛ کمی verboseتر.
- پ) عدم تغییر — چون کد خروج صحیح است و اثر فقط زیبایی گزارش است.

**پیشنهاد من:** گزینهٔ الف (یا ب) — یک خط جابه‌جایی، بدون اثر روی تصمیم/ران‌تایم معاملاتی؛ با توجه به S3 در اولویت پایان صف قرار گیرد.

**آزمون پذیرش و رگرسیون:** پذیرش: `run_apex.py boot --env-file <bad.env>` برای هر سه سناریوی probe باید exit 1 با سطر stdout `ERROR ValueError: malformed .env line 1: expected NAME=VALUE` (بدون traceback روی stderr) بدهد. رگرسیون`: اجرای `python3 -m pytest -q -p no:cacheprovider tests/unit/test_config.py` (در صورت وجود) و اجرای موفق `run_apex.py status` با `.env` سالم و بدون `.env`؛ آزمون‌های موجود که روی خروجی `status`/`bootstrap` سوارند نباید بشکنند.



