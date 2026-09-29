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
| C-005 | تأیید | S2 | S2 | نه (apex/ops/ فریز نیست) | C-015, D50, ISSUE-075 (تقویت اثر آن) | الف (نگاشت disposition) با ابزار ب (ویژگیٔ retryable در cursor) |
| C-007 | تأیید | S2 | S2 | نه | D51 (متریک)، ISSUE-075 (کد خروج) | الف (متریک‌های تفکیکی + اثر ناسالم‌بودن چرخه در exit) |
| C-009 | تأیید | S1 | S1 | **بله — بخش اصلی در apex/research/bootstrap.py (فریز)**؛ راه‌حل بیرون‌از‌فریز در لایهٔ service وجود دارد | — | ب (نگاشت صریح plugged در wiring + مدیریت SKIP_NIGHTLY در service) |
| C-011 | تأیید | S2 | S2 | بله — علت اصلی در bootstrap.py (فریز)؛ جبران service-layer ممکن | K-020 | ب |
| C-014 | تأیید | S2 | S2 | بله — علت اصلی در bootstrap.py (فریز)؛ جبران service-layer ممکن | G-005*، K-020 | ب |
| C-015 | تأیید | S2 | S2 | نه | C-005, D51 (HANDOFF_CP9:934) | الف (release در مسیر exception اثباتاً-پیش‌ارسال + علت‌ثبت) |
| O-006 | تأیید (راستی‌آزمایی شواهد؛ ردیف توافق دامنه، بدون ادعای نقص) | S4 | S4/غیرنقص | نه (params نسخه‌دار FROZEN_BOOTSTRAP؛ کد غیرفریز) | D51 (HANDOFF_CP9:935)، خانوادهٔ C-007/C-015 | الف+ب (سند دامنه + تست پین) |
| V-003 | تأیید (وصل‌بودن اتصال؛ بدون ادعای صحت محاسبات) | S4 | S4/کنترل تأییدشده | نه (همهٔ مسیرهای خوانده‌شده غیرفریز) | C-002 (مانع شاهد نهایی)، D-001/D-002، E-016، H-007 | ب (تست پین دائمی) + الف (تصریح سندی DECLARED_SKIP) |

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

**آزمون پذیرش و رگرسیون:** پذیرش: `run_apex.py boot --env-file <bad.env>` برای هر سه سناریوی probe باید exit 1 با سطر stdout `ERROR ValueError: malformed .env line 1: expected NAME=VALUE` (بدون traceback روی stderr) بدهد. رگرسیون`: اجرای `python3 -m pytest -q -p no:cacheprovider tests/unit/test_config.py` (۱۴ آزمون، در این نشست سبز شد) و اجرای موفق `run_apex.py status` با `.env` سالم و بدون `.env`؛ آزمون‌های موجود که روی خروجی `status`/`bootstrap` سوارند نباید بشکنند.

---

### C-005 — cursor برای HALTED/BLOCKED نیز جلو می‌رود

**ادعای ممیز (نقل کوتاه):** «cursor برای HALTED/BLOCKED نیز جلو می‌رود؛ فقط catch-up و preparation failure مستثنا هستند. BOOT_NOT_READY، TRADE_BUDGET_REACHED یا خطای بعدی می‌تواند آن close را تا مرز بعدی غیرقابل پردازش مجدد کند؛ برای TF ماهانه تأخیر بالقوه طولانی است» (`apex/ops/paper_loop.py:980–987,1047–1057`؛ شدت S2؛ جدید).

**آنچه خواندم:**
- `apex/ops/paper_loop.py:1–1192` (فایل کامل). فیلتر سلول‌های due در `run_cycle` (خطوط 982–990): اگر `_last_close[cell_id] >= close` آیتم به `already` می‌رود و در `due` قرار نمی‌گیرد (`cells_skipped_already_decided`). حلقهٔ به‌روزرسانی cursor (خطوط 1047–1057): روی **همهٔ** `runs` — فقط `run.cell_id in self._catch_up_failed or in self._context_preparation_failed` مستثناست — `upsert_cell_cursor` با `max(_last_close, close_ms)` صدا زده می‌شود. `upsert_cell_cursor` (خطوط 237–249) نگهبان `WHERE excluded.close_ms >= cell_decision_cursor.close_ms` دارد (هرگز عقب نمی‌رود).
- وضعیت‌های سلول از `apex/scheduler/clock.py:1–663` (فایل کامل): `CellRun.status` ∈ COMPLETE (هر نه stage PASS) / HALTED (stage FAIL یا UNAVAILABLE) / BLOCKED (drift block در خطوط 535–551 — هیچ stage اجرا نمی‌شود). فراخوانندهٔ تولیدکنندهٔ `runs`: `run_cycle` خودش (taskها در خط 1032 و gather در 1035).
- فراخوانندگان cursor: `load_cell_cursor`/`upsert_cell_cursor` فقط در `paper_loop.py` (`_load_cursor` خط 978–980 و حلقهٔ 1047–1057) و تست‌ها (`grep -rn` در کل مخزن). جدول `cell_decision_cursor` با مهاجرت افزایشی `M101_cp146_cell_decision_cursor` (خطوط 79–86) ساخته می‌شود.
- تست موجود `test_cp14_preparation_failure_isolated_retry_same_close_and_no_stale_source` (tests/integration/test_ops_paper_loop.py:886–922) دقیقاً استثنای preparation را پین می‌کند: پس از شکست prepare، `"BTCUSDT:1h" not in h.runtime._last_close` و چرخهٔ بعدی همان close را دوباره اجرا می‌کند — یعنی رفتار «retry استثناها» آگاهانه تست شده، اما برای HALTهای دیگر هیچ تست retry وجود ندارد.
- تصمیم D50 در `PHASE2_DECISION_LOG.md:1159` (نقل کامل در بخش قرارداد پایین).

**بازتولید:** `python3 AUDIT/probes_V1c/C-005.py` (خروجی خام `AUDIT/probes_V1c/C-005.out`) — فقط کد واقعی مخزن (SQLiteStore + LedgerWriter + PaperRuntime روی FixtureClock، بدون شبکه):
- فاز ۱: boot با `drift_seconds=None` → `boot_state=DEGRADED, new_trades_allowed=False`؛ چرخهٔ ۱ روی close `START_MS+HOUR`: سلول با **BOOT_NOT_READY** در stage execution → `HALTED`، اما `load_cell_cursor` نشان داد `{'BTCUSDT:1h': 1767229200000}` — cursor برای سلول HALTED جلو رفت؛ ۰ ارسال به adapter.
- فاز ۲: boot دوباره با drift=0 → READY؛ چرخهٔ ۲ روی **همان** close: `due=0`، `cells_skipped_already_decided=1`، صفر submission — close هالتی‌شده هرگز بازنگری نشد.
- فاز ۳: close بعدی (مرز ساعت بعد) دوباره عادی اجرا و COMPLETE شد — قفل فقط «تا مرز TF بعدی» نه تا ابد است.
- `CLAIM_REPRODUCED=True`. همچنین از خواندن `run_cell` در clock.py مشخص است BLOCKED (drift) هم از همان مسیر cursor عبور می‌کند چون حلقهٔ 1047 وضعیت را نمی‌سنجد.

**حکم و دلیل:** **تأیید**. رفتار دقیقاً همان است که ممیز نوشت: تنها استثناها catch-up و context-preparation هستند؛ HALT (هر دلیلی از جمله BOOT_NOT_READY و TRADE_BUDGET_REACHED) و BLOCKED cursor را به آن close می‌رسانند و فیلتر due آن close را «already decided» نگه می‌دارد. probe مستقل روی کد واقعی نشان داد close هالتی‌شده در چرخهٔ after-READY دیگر دیده نمی‌شود. شدت مستقل = S2، هم‌راستا با ممیز: اثر واقعی (ازدست‌رفتن close برای پردازش معاملاتی) اما محدود به یک دامنهٔ TF و قابل‌بازیابی در مرز بعدی.

**علت ریشه‌ای:** حلقهٔ قفل D50 بین «تصمیم قطعی گرفته‌شده» و «تلاش ناموفق/مسدودشده» تمایز قائل نمی‌شود؛ شرط معافیت فقط دو failure mode جدید CP-14 است و مابقی HALTها (که هیچ submission هم نکرده‌اند) همان مسیر COMPLETE را طی می‌کنند. فقدان یک disposition مصوب («این HALT قابل‌retry است/نیست») در `CellRun`.

**اثر مستقیم:** هر close که سلول در آن HALT/BLOCK شود (BOOT_NOT_READY — که در وضعیت فعلی دستگاه طبق ISSUE-075 پیش‌فرض بوت PAPER است —، TRADE_BUDGET_REACHED، NO_MARKET_DATA، PLAN_*، خطاهای runtime) تا **مرز TF بعدی** برای آن سلول از صف پردازش حذف می‌شود؛ برای 1m یک دقیقه، برای 1mo تا یک ماه. هیچ سفارش تکراری رخ نمی‌دهد (D50 حفظ است)، اما فرصت/الزام پردازش آن close از دست می‌رود.

**اثرات ثانویه و تعاملات (بالادست/پایین‌دست):**
- بالادست: بوت DEGRADED (ISSUE-075/C-002، تأییدشده در V1a) این نقص را از حاشیه به مسیر اصلی می‌آورد — هر closeی که در پنجرهٔ «boot نه READY» بیفتد قفل می‌شود. سیاست drift block (clock.py) هم BLOCKED تولید می‌کند که همین اثر را دارد.
- پایین‌دست: تعامل با C-015 کشنده‌تر است: اگر خطای پیش‌ارسال یک سلول، slot را بسوزاند و سلول‌های سالم همان چرخه TRADE_BUDGET_REACHED بگیرند، آن سلول‌های سالم *هم* به‌خاطر این ردیف cursor می‌گیرند و closeشان کاملاً سوخته می‌شود (نه فقط به چرخهٔ بعد موکول). catch_up دوباره بارها را می‌آورد اما تصمیم آن close تکرار نمی‌شود.
- دفترکل/هویت: تغییری نمی‌کند؛ ردیف trade_plan/fill برای سلول هالتی‌شده نوشته نمی‌شود (جز در سناریوی C-015 که materialize پیش از exception رخ داده).
- replay/آموزش: اثر ندارد (جدول cursor در مسیر replay مصرف نمی‌شود — مصرف‌کنندگان فقط paper_loop است، grep تأیید شد).

**نسبت با قرارداد و تصمیم‌ها:** D50 (`PHASE2_DECISION_LOG.md:1159`): «The per-cell close lock is the durable table `cell_decision_cursor` … a new `PaperLoop` on the same store does not decide the same close again. An older close does not rewind the lock.» — متن D50 فقط از **منع تصمیم تکراری** سخن می‌گوید و نمی‌گوید کدام خروجی (COMPLETE/HALT/BLOCK) «تصمیم» محسوب می‌شود؛ پس پیاده‌سازی فعلی *متخلف از حرف* D50 نیست بلکه در **خلا تصمیم** است: retry policy برای HALT تعریف نشده. بند §9.5-14 قرارداد (نقل در docstring clock.py) فقط ترتیب stageها را الزام می‌کند. نتیجه: ادعای ممیز «سیاست retry نیازمند تطبیق با D50» دقیق است و این ردیف را با تقدمِ تحلیل روی D50، تصمیم‌نیاز (design-gap) می‌دانم نه نقض صریح.

**فریز و راه‌حل بیرون از فریز:** `apex/ops/paper_loop.py` و `apex/scheduler/clock.py` فریز نیستند (فریز: engines/**، data_catalog/**، research/bootstrap.py، backtest.py، شش YAML، requirements.lock). DDL جدول `cell_decision_cursor` خود محصول مهاجرت افزایشی غیرفریز است؛ هر دو اصلاح ممکن‌اند بدون حکم مالک، اما *سیاست* retry طبق D50/DXX نیازمند تصمیم مالک است.

**گزینه‌های اصلاح:**
- الف) cursor فقط برای COMPLETE و HALTهای «تصمیم قطعی» (مثل DECISION_NO_TRADE یا PLAN_REJECTED_BY_RISK) جلو برود؛ HALTهای موقت (BOOT_NOT_READY, TRADE_BUDGET_REACHED, NO_MARKET_DATA, خطاهای runtime) cursor نگیرند. اثرات جانبی: (۱) چرخهٔ بعدی همان close را retry می‌کند — ریسک سفارش تکراری؟ خیر چون idempotency در PLAN_ALREADY_MATERIALIZED و intent_id content-hash (D50) باقی است؛ (۲) رفتار آزمون‌های موجود: `test_trade_budget_stops_the_cycle` و `test_a_degraded_boot_refuses_to_trade` فقط دلیل HALT را assert می‌کنند و cursor را نمی‌سنجند — نمی‌شکنند؛ (۳) در مهاجرت DB تغییری لازم نیست؛ (۴) باید مصوب شود کدام HALT «قطعی» است تا چرخهٔ بی‌پایان retry برای refusal‌های همیشگی (مثلاً NO_PLAN_FOR_CELL) رخ ندهد — معیار پیشنهادی: CellRefusalهای «تصمیمی» (decision/refusal دائمی آن close) قفل شوند، بقیه نه. BOOT_NOT_READY پس از readyشدن بوت باید دوباره ببیند؟ بله — همان چیزی که اپراتور انتظار دارد.
- ب) در cursor فیلد وضعیت/disposition ثبت شود (مثلاً `decided_kind`) تا retry سیاست‌مند شود. اثر: مهاجرت افزایشی جدید + مصوبهٔ مالک برای جدول؛ آموزش/هش دست‌نخورده.
- پ) وضع‌فعلی + مستندسازی «close هالتی‌شده سوخته است»: ارزان اما ناسازگار با انتظار عملیاتی و کنندهٔ اثر ISSUE-075.

**پیشنهاد من:** الف پیاده شود (بدون مهاجرت، در لایهٔ غیرفریز)، با لیست مصوبِ refusalهای «قطعی»؛ ب به‌عنوان بهبود بعدی اگر مالک خواست audit trail روی cursor. هم‌زمان با اصلاح C-015 تا تعامل «سوختن دوباره» از بین برود.

**آزمون پذیرش و رگرسیون:** پذیرش: probe فعلی C-005 باید پس از اصلاح در فاز ۲ نتیجهٔ متفاوت بدهد (`due=1` و HALT تکراری BOOT_NOT_READY یا پس از READY شدن، اجرای واقعی)؛ سناریوی TRADE_BUDGET_REACHED: با budget=1 و دو سلول، سلول دوم cursor نگیرد و در چرخهٔ بعد با budget تازه اجرا شود — بدون duplicate submission (assert روی `trade_plan` count و adapter calls). رگرسیون: `python3 -m pytest -q -p no:cacheprovider tests/integration/test_ops_paper_loop.py tests/unit/` (به‌ویژه test_ops_paper_loop که رفتار cursor/preparation را پین می‌کند).

---

### C-015 — خطای پیش‌ارسال slot بودجهٔ چرخه را تا پایان چرخه نگه می‌دارد

**ادعای ممیز (نقل کوتاه):** «D51 می‌گوید slotِ ارسالِ خارج‌نشده از process آزاد شود، اما `_stage_execution` پس از `_take_budget` فقط در صورت برگشت عادیِ `execute_plan` با `submitted=False` release می‌کند؛ برای exception حتی پیش از `append_trade_plan`/ارسال، slot می‌ماند … سلول اول با `OSError` تزریقی پیش از ارسال به `_budget_taken=1` رسید و سلول دوم بدون فراخوانی `execute_plan` به `TRADE_BUDGET_REACHED` خورد» (`apex/ops/paper_loop.py:527–543,620–646,692–705`؛ `apex/execution/fsm.py:530–567`؛ `PHASE2_DECISION_LOG.md:1161`؛ `PHASE2_HANDOFF_CP9.md:933–935`؛ شدت S2).

**آنچه خواندم:**
- `apex/ops/paper_loop.py:1–1192` (فایل کامل). `_take_budget`/`_release_budget` در خطوط 527–543؛ تنها فراخوانندهٔ `_take_budget` خط 638 در `_stage_execution` (620–646) و تنها فراخوانندهٔ `_release_budget` خط 641: `if not record.get("submitted"): self._release_budget()` — این خط فقط وقتی اجرا می‌شود که `execute_plan` **عادی برگردد**؛ exception از خط 638 (`record = await self.execute_plan(...)`) مستقیم به caller (Scheduler._run_cell_inner) پرتاب می‌شود و stage به FAIL می‌رسد (`clock.py:640–648`). بازنشانی بودجه در آغاز `run_cycle` خط 961 (`self._budget_taken = 0`).
- `execute_plan` (paper_loop.py:692–758): ساخت `ExecutionFSM` و `machine.submit`.
- `apex/execution/fsm.py:1–1362` (فایل کامل). `submit` (خطوط 530–567): ترتیب = validation → `append_trade_plan` (**قبل** از ارسال) → `advance("SUBMIT_ORDER")` (READY→SUBMITTING) → `adapter.submit_order`. هر exception در سه گام آخر از submit خارج می‌شود (هیچ try در مسیر نیست). فراخوانندگان submit: `execute_plan`، `manage_positions` (غیرمستقیم)، demo، تست‌ها.
- تست مرتبط موجود `test_trade_budget_stops_the_cycle` (tests/integration/test_ops_paper_loop.py:722–750) فقط مسیر عادی رزرو/آزادی را پین می‌کند؛ آزمون exception-پس‌از-رزرو وجود ندارد (`grep -rn '_release_budget\|_take_budget' tests/` → فقط همان تعریف usage در test budget معمولی).
- D51 در `PHASE2_DECISION_LOG.md:1161` و تکرار مصوب در `PHASE2_HANDOFF_CP9.md` خط 934 (نقل کامل پایین).

**بازتولید:** `python3 AUDIT/probes_V1c/C-015.py` (خروجی خام `AUDIT/probes_V1c/C-015.out`) — فقط کد واقعی مخزن؛ adapter دوبل تستی است که پیش از هر ارسال `OSError` می‌دهد (start trigger ممیز را با همان حدچارچوب بازتولید می‌کند):
- `budget=1`، سلول BTC: چرخهٔ ۱ → `HALTED` با `STAGE_FAILED:execution` و detail `'OSError: simulated pre-send transport failure (no bytes sent)'`؛ پس از چرخه: **`_budget_taken=1`** — slot آزاد نشد.
- `PlanQueue.counts()` → `{'materialized': 1, 'sent: 1}` و ledger صرفاً `['TRADE_PLAN', 'FSM_TRANSITION']` را دارد — یعنی طرح pre-send materialize و FSM به SUBMITTING رفت، ولی `adapter.submitted == []` (هیچ بایتی به «صرافی» نرسید). نکتهٔ جنبی: «sent» در counts عملاً معادل «رویداد TRADE_PLAN در ledger» است نه تأیید ارسال واقعی.
- سلول دوم (ETH سالم): فراخوانی مستقیم `_stage_execution` واقعی → `CellRefusal TRADE_BUDGET_REACHED (max_trades_per_cycle=1)` **بدون** ورود به `execute_plan` و بدون هیچ trade_plan/ارسال — دقیقاً رفتار گزارش‌شدهٔ ممیز.
- تعامل با C-005 در همان probe دیده شد: cursor سلول هالتی‌شده قفل شد (`{'BTCUSDT:1h': 1767229200000}`).
- چرخهٔ بعد (مرز ساعت بعد): بازنشانی D51 تأیید شد (`_budget_taken=0`) — نشت slot **درون همان چرخه** است نه فراتر از آن. (HALT چرخهٔ دوم در probe من PLAN_CELL_MISMATCH است؛ نقص fixture خودم — plan پیش‌فرض BTC را به سلول ETH دادم — و نقص محصول نیست؛ گیت symbol/cell درست کار کرد.)
- `CLAIM_REPRODUCED=True`.

**حکم و دلیل:** **تأیید**. مسیر exception پس از رزرو، release ندارد و slot تا پایان چرخه محروق می‌ماند؛ سلول سالم همان چرخه بدون فراخوانی execute_plan بودجه‌گریزی می‌شود. شدت مستقل = S2 هم‌راستای ممیز: اثر درون یک چرخه محدود است (بازنشانی D51 در چرخهٔ بعد)، اما عدالت بین سلول‌های due همان چرخه را نقض و — در ترکیب با C-005 — close سلول قربانی را نیز می‌سوزاند. دامنهٔ شاهد: trigger مصنوعی است؛ روی ToobitAdapter تولیدی خطاهای transport به AdapterResult UNKNOWN تبدیل می‌شوند و raise نمی‌کنند، بنابراین سناریوهای واقعی exception در این شکاف، خرابی‌های محلی (sqlite/دیسک پر، bus publish، باگ داخلی) هستند — روی گوشی Termux که موضوع storage guard دارد سناریوی دیسک‌پر غیرمحتمل نیست، اما در این sandbox روی ledger/شبکهٔ واقعی بازتولید نشده است.

**علت ریشه‌ای:** قرارداد مالک (D51) سه‌حالتهٔ «پیش‌ارسال / نامعلوم / ارسال‌شده» را به یک عبارت واحد «did not leave the process» خلاصه کرده و پیاده‌سازی آن را فقط در مسیر برگشت عادی (`submitted=False`) تحقق داده؛ هیچ مدیریت exception دور گام رزرو→execute_plan نیست (نه try/except، نه ثبت attempt). نقطه‌ای دقیق: از `_take_budget()` (paper_loop.py:638) تا بازگشت `execute_plan:` هر exception، بدون تعیین‌تکلیف slot، stage را می‌شکند.

**اثر مستقیم:** سوختن سهمیهٔ معاملهٔ سلول‌های سالم **همان چرخه** توسط یک خطای موضعی یک سلول (budget≠retryable درون چرخه). همراهی با C-005 اثر را تشدید می‌کند: سلولی که به‌خاطر نشت slot به TRADE_BUDGET_REACHED خورد، cursor هم می‌گیرد و closeش تا مرز TF بعدی می‌سوزد.

**اثرات ثانویه و تعاملات (بالادست/پایین‌دست):**
- بالادست: هر منبع exception بین رزرو و بازگشت execute_plan (ledger/دیسک، bus، adapter)؛ بالادستِ سیاستی: D51 خود پیش‌بینی release را کرده؛ انتخاب max_trades_per_cycle=4 (O-006) حساسیت به نشت را کاهش می‌دهد ولی حذف نمی‌کند.
- پایین‌دست: (۱) trade_plan ردیف materializeشده‌ای باقی می‌ماند که venue هرگز ندیده — در retry، گیت `PLAN_ALREADY_MATERIALIZED` همان plan را برای همیشه می‌بندد (اثر دائمی‌تر از خود نشت slot؛ نزدیک به دامنهٔ E-016/D-001، در این نشست بازبینی نمی‌شود). (۲) FSM در SUBMITTING نیمه‌کاره می‌ماند؛ check_timeouts/recovery ممکن است آن را به RECOVERY_REQUIRED ببرد. (۳) متریک‌ها (C-007) این تلاش را به‌عنوان trade نمی‌شمارند (record ساخته نشد) — پس نشت در شمارش‌ها هم نامرئی است (فقط در halt_reasons به شکل STAGE_FAILED دیده می‌شود).
- روی هش/هویت: intent_id از content hash (D50) تغییر نمی‌کند؛ ledger chain سالم ماند (probe: intact=True).

**نسبت با قرارداد و تصمیم‌ها:** D51 (`PHASE2_DECISION_LOG.md:1161`): «…`max_trades_per_cycle` resets at the start of every cycle. The reservation is synchronous … taken only when a valid trade plan exists, immediately before admission. … **A submission that does not leave the process releases the slot.**» و تکرار مصوب `PHASE2_HANDOFF_CP9.md:934`. متن حکم صریح است و پیاده‌سازی فعلی در مسیر exception با حرف D51 **ناسازگار** است (یک submission که «از process خارج نشده» شامل exception پیش‌ارسال هم می‌شود). ممیز درست متوجه شده که copy صریحِ «release در finally» خطرناک است: اگر exception *پس از* خروج درخواست رخ دهد (پاسخ مبهم)، آزادسازی slot = شمارش دوبرابری ظرفیت و در عمل عبور از سقف چرخه؛ لذا اصلاح باید تفکیک‌دار باشد.

**فریز و راه‌حل بیرون از فریز:** `apex/ops/paper_loop.py` و `apex/execution/fsm.py` فریز نیستند؛ تغییر بدون حکم مالک ممکن است، اما چون معنای D51 لمس می‌شود، خوانش نهایی «کدام exception پیش‌ارسال محسوب می‌شود» بهتر است با مالک تثبیت شود.

**گزینه‌های اصلاح:**
- الف) در `_stage_execution` دور `execute_plan` try/except: خطاهای اثباتاً پیش‌ارسال (پیش از `append_trade_plan` — مثلاً با فلگ زمانی که هنوز trade_plan نوشته نشده، یا exceptionهای محلی شناخته‌شده مثل sqlite/validation) → `_release_budget()` + ثبت علت و سپس re-raise تا HALT بماند. اثرات جانبی: آزمون جدید لازم؛ ریسک دسته‌بندی اشتباه exception → رهاسازی نادرست؛ فقط exceptionهای whitelistشده آزاد شوند. بدون مهاجرت DB و بدون تغییر هش.
- ب) ثبت وضعیت attempt سه‌حالته (pre-send/unknown/sent) در رکورد چرخه و آزادسازی فقط در حالت pre-send اثبات‌شده؛ حالت unknown تا reconcile قفل. اثر: کد بیشتر، اما با خطر «finally کور» ممیز سازگارتر است (prevents double-submit capacity).
- پ) وضع فعلی + اعلان: چون بازنشانی چرخه‌ای است، بعضی تیم‌ها ممکن است بپذیرند؛ اما با C-005 ترکیب می‌شود و close می‌سوزاند — توصیه نمی‌کنم.

**پیشنهاد من:** الف در کوتاه‌مدت (whitelist پیش‌ارسال + release + ثبت علت در `cycle` و refusals)، به‌همراه جداکردن ردیف materializeنشدهِٔ plan از sent در گزارش‌دهی (به‌عنوان بخش اطلاع‌رسانی، نه منطق). ب به‌عنوان مسیر رسمی با تصمیم مالک، به‌ویژه که ردیف trade_planِ materializeشده-بدون‌ارسال سرنوشت E-016 را هم روشن می‌کند.

**آزمون پذیرش و رگرسیون:** پذیرش: budget=1 + exception پیش‌ارسال در سلول ۱ → `_budget_taken==0` پس از HALT و سلول ۲ سالم می‌تواند ارسال کند (execute_plan فراخوانی می‌شود)؛ exception پس از ارسالِ نامعلوم → slot حفظ شود. persistence: هیچ DOUBLE release (budget منفی نشود — assert `_budget_taken>=0`). رگرسیون: `tests/integration/test_ops_paper_loop.py` کامل + `tests/unit/test_execution_fsm.py` (ماتریس FSM دست‌نخورده می‌ماند؛ اصلاح در paper_loop است).

---

### C-007 — submission ردشده cell را COMPLETE و شمارش trade را گمراه‌کننده می‌کند؛ exit code فقط بوت را می‌سنجد

**ادعای ممیز (نقل کوتاه):** «submission ردشده می‌تواند بدون exception مرحلهٔ execution را تمام و cell را COMPLETE کند؛ `cycle.trades` تعداد COMPLETE است، نه fill/submit موفق. کد خروج serve نیز فقط boot اولیه را می‌سنجد، حتی اگر outcome زنجیرهٔ ناسالم گزارش کند» (`apex/ops/paper_loop.py:638–646,723–727,1031–1058,1126–1133`؛ `scripts/run_apex.py:791–807`؛ شدت S2).

**آنچه خواندم:**
- `apex/ops/paper_loop.py:1–1192` (فایل کامل): در `_stage_execution` (620–646) مسیر `not record["submitted"]` فقط `_release_budget()` می‌کند و stage **نرمال برمی‌گردد** (خطوط 641–646)؛ در `execute_plan` (692–758) مسیر `not accepted` (724–727) رکورد را در `self.refusals` و `self.trades` می‌نشاند و بدون exception برمی‌گردد؛ در `run_cycle` خط 1058: `cycle["trades"] = [r for r in runs if r.status == "COMPLETE"]`؛ در `run` (1102–1133) خروجی: `{"cycles": rounds, "trades": len(self.trades), "refusals": len(self.refusals), ...}`.
- معنای COMPLETE از `apex/scheduler/clock.py:590–610`: هر نه stage باید PASS شوند؛ failure → HALTED. پس COMPLETE-at-execution + submitted=False ممکن است (PASS برگرفته از «نداشتن exception» است، نه «موفقیت سفارش»).
- `scripts/run_apex.py:746–806` (فایل کامل خوانده شد): `_serve` خط 791 `outcome = await driver.run(...)` را اجرا و خلاصه را چاپ می‌کند (793–804) و خط 806 `return EXIT_READY if boot["boot_state"] == "READY" else EXIT_DEGRADED` — هیچ‌یک از فیلدهای outcome (trades/refusals/ledger/chain) در exit code وارد نمی‌شود. فراخوانندهٔ `_serve`: فقط `main` (خط 1151–1154).
- REFUSED واقعی محصول: `apex/execution/toobit_adapter.py:829–835` شکل واقعی `classification="REFUSED", outcome="REJECTED"` را می‌سازد (گارد داخلی adapter) — بنابراین سناریوی این ردیف صرفاً تئوریک نیست.
- تست‌ها: `grep -rn 'submitted.*False\|REFUSED_BEFORE' tests/integration/test_ops_paper_loop.py tests/integration/test_cp7_paper_loop.py` → هیچ تستی CELL-COMPLETE-without-submission یا خروجی exit serve را پین نمی‌کند.

**بازتولید:** `python3 AUDIT/probes_V1c/C-007.py` (خروجی خام `AUDIT/probes_V1c/C-007.out`) — کد واقعی + adapter دوبل که همهٔ ارسال‌ها را با شکل REFUSED واقعی adapter رد می‌کند:
- سلول BTC با plan معتبر: **`cells_complete=1, cells_halted=0`** و `len(cycle['trades'])=1`، درحالی‌که `runtime.trades[-1]` حاوی `submitted=False, outcome=REJECTED, reason=REFUSED_BEFORE_SUBMISSION, fill=None`.
- `adapter.submitted == []` — هیچ بایتی به «صرافی» نرسید (گارد داخلی adapter رد کرد)؛ `queries` فقط دو query بوت (open/fills) بود.
- `runtime.run(cycles=1)` بیرون‌رفت: `outcome: cycles=1, trades=1, refusals=3, boot_state=READY, chain=True` → **متریک `trades=1` درحالی‌که صفر سفارش فرستاده شد**. (2 refusal دیگر، failureهای publisher دوره‌ای sandbox-بی‌شبکه است؛ حذفشان تصویر را عوض نمی‌کند.)
- `CLAIM_REPRODUCED=True`. بخش کد خروج serve: ران‌کردن کامل `_serve` نیازمند credential واقعی/شبکه است (خارج از محدوده)؛ ادعا را به شکل استاتیک در خط 806 راستی‌آزمایی کردم — گزاره‌بولی فقط `boot["boot_state"]` است و boot در خط 767 (`boot = await driver.boot(...)`) **پیش از** حلقهٔ چرخه‌ها محاسبه می‌شود؛ پس ناسالم‌بودن زنجیرهٔ چرخه‌ها روی exit بی‌اثر است (با فرض READY بودن بوت).

**حکم و دلیل:** **تأیید** هر سه جزء ادعا: (الف) REFUSED-submission بدون exception به COMPLETE سلول می‌انجامد؛ (ب) `cycle.trades`/`outcome['trades']` به‌جای «سفارش موفق»، «سلول COMPLETE / رکورد تلاش» را می‌شمارد (دقت: ارقام کاملاً صادقانه در فیلدهای دیگر — `refusals`, `halt_reasons`, رکورد trade با submitted=False — افشا می‌شوند؛ مسئله «هم‌معنایی ارقام» است نه پنهان‌کاری)؛ (پ) exit code serve فقط خروجی بوت اولیه است. شدت مستقل = S2 هم‌تراز با ممیز: پایش/پذیرش PAPER روی ارقامی تکیه می‌کند که در سناریوی «همهٔ ارسال‌ها رد» به‌نظر موفق می‌آیند، اما چون refusalها هم‌زمان ثبت می‌شوند و کد خروج با docstring خود فایل («0 = READY») بیانگر بوت نه سلامت چرخه است، به S1 نمی‌رسد.

**علت ریشه‌ای:** در `execute_plan` مسیر not-accepted به‌عنوان «پایان موفق stage» مدل شده (refusalها فقط در لیست refusals می‌نشینند، stage PASS می‌ماند) و معیار COMPLETE سلول «بدون-exceptionبودن» است؛ در لایهٔ گزارش‌دهی، trades به‌جای شمارش submitted/filled روی وضعیت سوار است؛ در لایهٔ CLI قرارداد exit code فقط روی verdict بوت بسته شده و هیچ کششی از `outcome['refusals']` یا نسبت cells_halted ندارد.

**اثر مستقیم:** (۱) در چرخه‌ای که چند submission رد شود، `trades=N` در خروجی serve/status چاپ می‌شود درحالی‌که صفر سفارش واقعی رخ داده — برای پایشگر خارجی «معاملهٔ موفق» تلقی می‌شود؛ (۲) exit code 0 با زنجیرهٔ کاملاً ناسالم (مثلاً همهٔ سلول‌ها NO_PLAN/provider refusal پشت‌سرهم) — اسکریپت systemd/supervisor ری‌استارت یا هشدار نمی‌دهد.

**اثرات ثانویه و تعاملات (بالادست/پایین‌دست):**
- بالادست: هر منبع REFUSED (guardهای adapter: امضا، پارامتر نادرست، disable شدن نماد)؛ D51 مالک بودجه را فقط روی submission معنادار ردکرده و نه fill — تغییر معیار trades روی بودجه اثر ندارد (budget با `_take_budget` جداست).
- پایین‌دست: پذیرش PAPER (سبزشدن) — اگر معیار پذیرش «trades>0» باشد ممکن است پذیرش کاذب شود؛ با ISSUE-075 (boot نه READY) ترکیب می‌شود: در وضعیت فعلی بوت DEGRADED است و exit=2 درست می‌آید، ولی روزی که C-002 اصلاح شود و بوت READY شود، چرخهٔ ناسالم exit 0 می‌گیرد. تعامل با C-015: رکورد exception-شده در trades نیامد (Record ساخته نشد) → متریک trades هم «هرکز نشت بودجه» را نشان نمی‌دهد.
- روی دفترکل/هویت/replay: بی‌اثر (ledger ورودی TRADE_PLAN خام را دارد؛ تفسیر «trade بودن» صرفاً در لایهٔ گزارش runtime است).

**نسبت با قرارداد و تصمیم‌ها:** docstring run_apex.py (خط 45–47): «Exit codes: 0 = READY, 2 = DEGRADED/refused…». این متن صریحاً سلامت *زنجیرهٔ چرخه* را موضوع exit نمی‌داند — بنابراین پیاده‌سازی با حرف docstring سازگار اما با روح «fail-closed, never a silent success» (خط 52) در تضاد خفیف است: موفقیت «سکوت‌آمیز» زمانی رخ می‌دهد که چرخه‌ها همه رد شوند و exit همچنان 0 باشد. در قرارداد (APEX_GEN5.md) بندی برای نگاشت سلامت چرخه→کد خروج پیدا نکردم (جست‌وجوی «exit code»/«کد خروج»). تصمیم مالکی هم در DECISION_LOG وجود ندارد؛ یعنی این ردیف design-gap است نه نقض متن مصوب. به همین دلیل پیشنهاد ممیز («readiness جاری و سلامت نهایی در exit status مؤثر شوند») نیازمند تصمیم مالک دربارهٔ آستانه است.

**فریز و راه‌حل بیرون از فریز:** هر دو فایل (`scripts/run_apex.py`, `apex/ops/paper_loop.py`) غیرفریزند؛ اصلاح آزاد است (به‌جز آن که تعریف آستانهٔ سلامت بهتر است مصوب مالک شود).

**گزینه‌های اصلاح:**
- الف) متریک‌های تفکیکی: `cycle["trades_submitted"]`, `["trades_filled"]`, `["trades_refused"]` جدا و چاپ هر سه در serve/status؛ `outcome['trades']` به submitted واقعی تغییر معنا دهد (شکننده برای مصرف‌کنندهٔ فعلی کلید trades — docs/tests به‌روزرسانی) یا بهتر: کلید جدید `trades_effective`. اثر جانبی: خروجی JSON متنی تغییر می‌کند — نسخه‌بندی/مستندسازی؛ آزمون‌های فعلی که فقط `outcome['cycles']`/`ledger_chain_intact` را سنجند نمی‌شکنند (`grep` در تست‌ها).
- ب) exit code حساس به سلامت: مثلاً `EXIT_READY` فقط اگر `boot READY` و `refusals==0 و halted_ratio==0` در چرخه‌های اجراشده (با آستانهٔ مصوب)؛ در غیر این صورت EXIT_DEGRADED. اثر جانبی: تغییر قرارداد خروجی CLI — supervisorها باید بازبینی شوند؛ سناریوهای رایج «یک refusal گذرا» ممکن است noise بدهد؛ نیازمند تصمیم مالک برای آستانهٔ قابل‌قبول (S2/S3 بودن سیاستی است نه فنی).
- پ) همان‌طور که ممیز گفت، «read-only cycle از trading success جدا» — جداسازی گزارش read-only (`--cycles` بدون submission) از گزارش trading. اثر: سطح API جدید.

**پیشنهاد من:** ترکیب الف (فوری، زیرساخت متریک) + ب پس از مصوبهٔ آستانه (مثلاً: exit≠0 اگر تمام سلول‌های due در آخرین چرخه refusal/halted بودند). تا قبل از آن، خروجی serve باید **کنار** `cycles/trades` یک سطر صریح `submitted=<n> refused=<m>` چاپ کند (تک‌خطی، بدون تغییر exit).

**آزمون پذیرش و رگرسیون:** پذیرش: probe C-007 باید پس از اصلاح نشان دهد `trades_submitted=0, trades_refused=1` و (پس از ب) exit serve در چرخهٔ تمام‌رد ≠0. رگرسیون: `python3 -m pytest -q -p no:cacheprovider tests/integration/test_ops_paper_loop.py tests/integration/test_cp7_paper_loop.py` و افزودن تست واحد روی نگاشت exit در `_serve` (با driver جعلی — مانند ساختار فعلی تست‌ها).

---

### C-009 — تفسیر بولی باتری و اجرای SKIP_NIGHTLY در bootstrap نادرست است

**ادعای ممیز (نقل کوتاه):** «دو شکست مستقل حفاظت باتری: `bool("UNPLUGGED")` و `bool("false")` در parser برابر True است (برای نمونهٔ ۴٪/UNPLUGGED، preflight پیوسته `PROCEED` داد)؛ حتی وقتی ورودی بولی unplugged و ۱۰٪ است و preflight `SKIP_NIGHTLY` می‌دهد، `run_phase1` فقط `PAUSE` را هندل می‌کند و fetch زده و `COMPLETE` می‌شود. `read_battery` نیز returncode ناموفق را بررسی نمی‌کند. تست موجود همین COMPLETE نادرست را انتظار دارد» (`apex/research/bootstrap.py:94–120,249–257`؛ `apex/ops/bootstrap_service.py:1089–1105,1410–1424`؛ `tests/unit/test_research_bootstrap.py:79–85,303–314`؛ شدت S1؛ «فرمت دستگاه احراز نشده»).

**آنچه خواندم:**
- `apex/research/bootstrap.py:1–438` (فایل کامل، **فریز**). `hardware_preflight` (73–101): `plugged = bool(battery.get("plugged"))` خط 94؛ شروط PAUSE/SKIP_NIGHTLY فقط وقتی `not plugged`. `parse_battery_json` (105–120): `{"percentage": data.get("percentage"), "plugged": bool(data.get("plugged"))}` — هر رشتهٔ غیرخالی (از جمله `"UNPLUGGED"` و `"false"`) → True. `run_phase1` (246–346): تنها شاخهٔ preflight خط 252 `if preflight["action"] == "PAUSE":` است؛ SKIP_NIGHTLY به مسیر عادی می‌افتد و حلقهٔ fetch اجرا و سلول‌ها COMPLETE می‌شوند. فراخوانندگان `hardware_preflight`/`parse_battery_json`: `apex/ops/bootstrap_service.py` (import خط 67–69) و تست‌ها.
- `apex/ops/bootstrap_service.py:1–1680` (فایل کامل، غیرفریز). `read_battery` (1089–1105): `subprocess.run(..., timeout=10)` بدون `check=True`؛ **هیچ ارجاعی به returncode نیست** — stdout به `parse_battery_json` می‌رود (1104). در `run` (1410–1424): `battery = read_battery()` و preflight برای اعلان محاسبه و سپس `run_phase1(..., battery=battery)` صدا زده می‌شود؛ هیچ شاخه‌ای برای SKIP_NIGHTLY در سطح service هم نیست.
- `tests/unit/test_research_bootstrap.py` در نقطه‌های استنادشده: تست `test_parse_battery_json` (79–81) **عمداً** `'{"percentage": 42, "plugged": "true"}' → plugged=True` را پین می‌کند — یعنی کوئرسیون رشته‌ای در طراحی تست هم هست، اما هیچ تستی برای `"UNPLUGGED"`یا `"false"` وجود ندارد؛ `test_battery_skip_is_honoured` (~312–326) با battery=10%/False صرفاً `result["status"] == "COMPLETE"` را assert می‌کند و تعداد fetch را نمی‌شمارد — دقیقاً همان چیزی که ممیز گفت.
- قرارداد W.6 در `APEX_GEN5.md:17278` (متن کامل پایین نقل شده) و قالب واقعی Termux از منبع مستقل (پایین).

**بازتولید:** `python3 AUDIT/probes_V1c/C-009.py` (خروجی خام `AUDIT/probes_V1c/C-009.out`) — import مستقیم توابع واقعی، بدون شبکه:
- (۱) JSON واقعی Termux با ۴٪ و `"plugged": "UNPLUGGED"` → parser خروجی داد `{'percentage': 4, 'plugged': True}`؛ سپس `hardware_preflight(continuous=True)` → **`action=PROCEED`** درحالی‌که کنترل بولی واقعی (`plugged: False`، ۴٪) → `PAUSE (CONTINUOUS_BATTERY_BELOW_5PCT)`. همچنین `"plugged": "false"` → True.
- (۲) با booleans درست (unplugged=False؟ خیر: `plugged=False`، ۱۰٪، حالت nightly): preflight درست `SKIP_NIGHTLY (BATTERY_BELOW_15PCT)` داد، اما `run_phase1` → **`status=COMPLETE` با ۲ فراخوانی fetch واقعی و ۱ ردیف ingest** — هیچ skipی رخ نداد.
- (۳) `read_battery` با runner جعلی rc=1 + stdout معتبر → JSON parse شد (`{'percentage': 3, 'plugged': True}`)؛ returncode خوانده نشد.
- `CLAIMS_REPRODUCED=True`.
- **فرمت دستگاه:** ممیز گفته بود «احراز نشده». من با منبع مستقل احراز کردم که `plugged` در خروجی termux-battery-status **رشته** است با مقادیر UNPLUGGED/PLUGGED_AC/PLUGGED_USB/PLUGGED_WIRELESS (مستندات بستهٔ gotermux که نوع فیلد را `Plugged string` با همین مقادیر معرفی می‌کند و با پیاده‌سازی BatteryStatus در termux-api منطبق است) [منبع: pkg.go.dev/github.com/hugmouse/gotermux]. پس مسیر مضر (Parser→True برای دستگاه unplugged) روی دستگاه واقعی با termux-api فعال است. شاهد نهایی از خود دستگاه با دستور فقط‌خواندنی `termux-battery-status` تکمیلی می‌ماند (نسخهٔ termux-api روی گوشی مالک می‌تواند فرق کند، هرچند بدبینانه‌ترین حالت رشته است).

**حکم و دلیل:** **تأیید** (هر سه ادعا + پین تست). شدت مستقل = S1 هم‌راستای ممیز: حفاظت W.6 در قالب واقعی دستگاه **معکوس** عمل می‌کند (به‌جای pause/skip، اجرای برداشت طولانی روی باتریٔ بحرانی شارژنشده) و پیامد آن خاموشی احتمالی میان‌نوشتن و فشار بر SQLite/بازیابی است — اختلال جدی در حفاظت/بازیابیِ مسیر برداشت. دو قید صداقت: (الف) اگر termux-api نصب نباشد، `read_battery` → None → «skip نکن» (W.6) — یعنی مسیر مضر به نصب‌بودن termux-api مشروط است؛ (ب) بخش returncode اثر عملی محدودتری دارد (stdoutِ معتبرِ battery-shape با خروج غیرصفر نادر است) و آن را S3/سندی جداگانه می‌دانم — اما دو پایهٔ اول S1 را تشکیل می‌دهند.

**علت ریشه‌ای:** سه لایه: (۱) مدل قرارداد در APEX_GEN5.md:17278 خود مبهم است — «`plugged` (truthy if charging)» انگاشته که Termux boolean می‌دهد، درحالی‌که رشتهٔ enum است؛ کد همان مدل نادرست را literal پیاده کرده (`bool()`). (۲) در runner فریز، واژگان action سه‌تایی است (PROCEED/PAUSE/SKIP_NIGHTLY) اما `run_phase1` فقط دو‌تایی طراحی شده: «PAUSE یا ادامه»؛ SKIP_NIGHTLY هرگز در نقشهٔ اجرا ترجمه نشده. (۳) در wiring، `read_battery` قرارداد «معتبر فقط با خروج موفق» را enforce نکرده.

**اثر مستقیم:** در حالت continuous با باتری <۵٪ (طراحی: PAUSE) → برداشت ادامه می‌یابد؛ در nightly با <۱۵٪ (طراحی: SKIP) → برداشت کامل اجرا و سلول‌ها COMPLETE علامت می‌خورند (وضعیت COMPLETE اشتباه در progress/status هم می‌نشیند چون واقعاً fetch شده، نه به‌خطای گزارش — ولی نسبت به نیت W.6 شب‌ skip این EN عملیات ممنوع بوده).

**اثرات ثانویه و تعاملات (بالادست/پایین‌دست):**
- بالادست: نصب termux-api (شرط فعال‌شدن)، سیاست W.6، و این واقعیت که service.run همان preflight را دوباره می‌سنجد (اصلاح در service پوشش مسیر production است اما مسیر مستقیم runner — مثلاً تست/RESEARCH — همچنان آسیب‌پذیر می‌ماند).
- پایین‌دست: خاموشی احتمالی میان‌رای SQLite در برداشت چندساعته (بازیابی تحت فشار — با ISSUE-077 مرتبط است اما هویت/هش raw دگرگون نمی‌شود؛ cursor دوام دارد و Phase 1 resume می‌کند)؛ کیفیت دادهٔ تحویلی به آموزش E11 اگر run در برق ناپایدار COMPLETE شود؛ status/Telegram گزارش COMPLETE برای شبی که باید SKIPPED می‌شد.
- تعامل: C-011 (گزارش پروگرس) و C-014 (resume بدون recheck) مجموعهٔ «بهره‌برداری برداشت» را کامل می‌کنند؛ K-020 (empty-page → COMPLETE بدون verifier) مستقل اما هم‌خانواده.

**نسبت با قرارداد و تصمیم‌ها:** `APEX_GEN5.md:17278`: «Hardware preflight (easy thresholds): pause if free disk < 512 MB. Nightly auto skip only if battery readable and < 15% and unplugged. Continuous pause only if < 5% and unplugged. Missing battery API → do not skip. Battery JSON, if present, is Termux termux-battery-status: fields percentage (number) and plugged (truthy if charging). Do not invent a percentage when the API is absent.» — حق با ممیز است: (الف) نسبت به *نیت* این بند («skip زیر ۱۵٪ unplugged»)، هر دو نقص نقض مستقیم‌اند؛ (ب) نسبت به *حرف* بند («truthy if charging»)، مدل قرارداد با قالب واقعی Termux ناسازگار است و کد از حرف پیروی کرده — یعنی قرارداد هم نیازمند اصلاح سندی است (نگاشت «charging ⇔ plugged ∈ {True, "true", 1} یا startswith("PLUGGED")»). تصمیم مؤخری در DECISION_LOG پیدا نکردم که این را باطل یا تغییر کند (D1–D61 دربارهٔ battery تصمیمی ندارند).

**فریز و راه‌حل بیرون از فریز:** `apex/research/bootstrap.py` **فریز است** (اصلاح parser/runner فقط با حکم مالک). راه‌حل بیرون‌از‌فریز در لایهٔ service موجود است: (الف) نگاشت صریح plugged در `read_battery` (bootstrap_service.py — غیرفریز) پیش از تحویل به runner: مقدار به True/False/None نرمال شود (UNPLUGGED→False، PLUGGED_*→True، boolean پاس‌-through، هر چیز دیگر→None با لاگ)؛ این تنها نقطهٔ ورود واقعی Termux است و runner همیشه mapping سالم می‌گیرد. (ب) مدیریت SKIP_NIGHTLY در `BootstrapService.run` (غیرفریز): اگر result preflight نهایی SKIP_NIGHTLY بود، اجرای run_phase1 صدا زده نشود و status گزارش «SKIPPED_NIGHTLY» شود — در عمل همان اثر را بدون دست‌زدن به فریز می‌دهد. قید: مسیر «فراخوانی مستقیم runner» بدون service همچنان نادرست می‌ماند و تست‌های فعلی که رفتار فریز-نادرست را پین کرده‌اند برای تصحیح نهایی نیازمند حکم مالک‌اند.

**گزینه‌های اصلاح:**
- الف) اصلاح فریز با حکم مالک: `plugged` با نگاشت صریح enum/bool و عبور SKIP_NIGHTLY از run_phase1 (status جدید «SKIPPED» — نه COMPLETE — با checkpoint دست‌نخورده). اثرات جانبی: تست‌های 79–81 و 312–326 باید بازنویسی شوند (همان‌ها امروز رفتار نادرست را پین کرده‌اند)؛ هیچ هش/هویت/کش اثر نمی‌گیرد؛ بدون مهاجرت DB.
- ب) فقط لایهٔ wiring (غیرفریز، بدون حکم مالک برای فریز): نگاشت صریح در `read_battery` + گیت SKIP_NIGHTLY در `BootstrapService.run`. اثر جانبی: سیاستسازی در لایهٔ wiring (پیش‌رمض CP-10/CP-11/CP-12/CP-13 است که دقیقاً برای همین کار طراحی شده)؛ رفتار تست‌های واحد runner فریز دست‌نخورده می‌ماند؛ اما تناقض runner-مستقیم باقی است و باید مستند شود.
- پ) هر دو.

**پیشنهاد من:** ب را فوری (بدون لمس فریز، همان‌جا که production قرار دارد `run_apex.py bootstrap` را می‌خواند) و الف را با حکم مالک در اولین پنجرهٔ تغییر فریز دنبال کنید؛ ضمناً متن 17278 قرارداد را با قالب واقعی Termux صریح کنید. تست‌های پین‌کنندهٔ رفتار نادرست را در همان حکم مالک اصلاح کنید.

**آزمون پذیرش و رگرسیون:** پذیرش: چهار سناریوی ممیز — (۱) ۴٪/UNPLUGGED در continuous ⇒ PAUSE (بعد از اصلاح wiring: `read_battery` خروجی False بدهد و preflight PAUSE شود)؛ (۲) ۱۰٪/False در nightly ⇒ هیچ فراخوانی fetch (`fetch_calls==0`) و status گزارش‌شده SKIPPED_NIGHTLY (نه COMPLETE)؛ (۳) plugged واقعی ⇒ ادامهٔ عادی؛ (۴) command ناموفق ⇒ battery=None (skip نکن). رگرسیون: `python3 -m pytest -q -p no:cacheprovider tests/unit/test_research_bootstrap.py tests/unit/test_ops_bootstrap_service.py` — پس از گزینهٔ ب، تست‌های موجود runner-فریز سبز می‌مانند؛ تست جدید wiring برای نگاشت plugged و شمارش fetch در حالت SKIP لازم است.











### C-011 — درصد پیشرفت و ETA «بوت‌استرپ» فاقد مبنای واقعی است

**ادعای ممیز (نقل کوتاه):** «`percent_complete` با مخرج فرضی `cells*8` (۱۴۰ سلول ⇒ هر ۸ صفحه یک سلول) محاسبه می‌شود درحالی‌که صفحات واقعی بر اساس جاری‌بودن `close_ms` کار می‌کنند؛ برای سلولی مانند 1m (بیش از ۸ صفحه) با رسیدن به ۱۱۲۰ صفحه، ۱۰۰٪ اعلام می‌شود درحالی‌که سلول‌ها pending هستند. `eta().measured` نیز نیازمند گذشت زمان از command('start') است و بدون آن `NO_MEASUREMENT_YET`» (`apex/research/bootstrap.py`؛ `apex/ops/bootstrap_service.py:1345–1383`؛ `scripts/run_apex.py:577–604`؛ شدت S2).

**آنچه خواندم:**
- `apex/research/bootstrap.py:1–438` (کامل، **فریز**): در `progress()`، `percent_complete = min(100.0, 100 * pages_fetched / (len(cells) * 8))` تنها شاخهٔ وقتی است که `pages_fetched > 0` — و **نکتهٔ بدتر: وقتی هنوز هیچ صفحه‌ای fetch نشده، تابع به‌جای ۰٪، ۱۰۰٪ برمی‌گرداند**. `pages_fetched` فقط یک شمارندهٔ درون‌حلقه (`+= 1` به‌ازای هر فراخوان fetcher) است و هرگز به «سلول تکمیل‌شده» تبدیل نمی‌شود؛ مخرج واقعی هر سلول (تعداد صفحات تا امروز) هیچ‌جا محاسبه نمی‌شود. با DEEP_START ≈ ۷ هفته، سلول 1m تقریباً ۱۴۴ صفحهٔ ۱۰۰۰تایی می‌خواهد در برابر «۱» صفحهٔ برآوردشدهٔ فرمول — انحراف سیستماتیک. `eta()` نیز `measured=True` فقط وقتی می‌دهد که `command("start")` ساعت را ثبت کرده باشد؛ پیش از آن `basis=NO_MEASUREMENT_YET` و `eta_seconds=None`.
- `apex/ops/bootstrap_service.py:1345–1383` (غیرفریز): `status_text()` همان `runner.progress()["percent_complete"]` را در قالب ««N% — current=…»» بدون هیچ بازچکشی در پیام وضعیت می‌گذارد؛ همان اعداد در `progress()/eta()` گزارش service و سپس در `_status` (`scripts/run_apex.py:577–604`) و اعلان‌های Telegram نشسته‌اند.
- تست‌های unit فعلی همان مخرج `len(cells)*8` را پین می‌کنند (مثلاً حساب `pages_fetched = cells * 8 / 2 ⇒ 50.0`)، یعنی ناسازگاری با صفحه‌بندی واقعی از سمت تست‌ها هم سنجیده نشده است.

**بازتولید:** `python3 AUDIT/probes_V1c/C-011.py` (خروجی خام `AUDIT/probes_V1c/C-011.out`; import مستقیم از کد واقعی، بدون شبکه):
- (الف) runner تازه، بدون هیچ صفحه و چک‌پوینت: `current_cell=None pages_fetched=0 → percent_complete=100.0` — اعلام «کامل» پیش از هر کاری.
- (ب) میان‌راه با `pages_fetched=1120 (=140*8)`: **`percent_complete=100.0`** درحالی‌که `pending_cells()` برابر `140/140` است؛ با ۵۶۰ صفحه دقیقاً ۵۰٪ — کاملاً متناسب با فرمولِ مصنوعی و نه واقعیت.
- (ج) ETA: پیش از `command("start")` → `basis=NO_MEASUREMENT_YET measured=False eta_seconds=None`؛ حتی با ۱۰ صفحهٔ fetch‌شده اما startِ نشده باز `measured=False`؛ پس از `command("start")` → `measured=True` و seconds_per_page محاسبه می‌شود — یعنی سازوکار اندازه‌گیری سالم است اما به شروعِ فرمانی گره خورده.
- `CLAIM_REPRODUCED=True`.
- قید صداقت دربارهٔ بخش «سلول 1m»ی ادعا: نمی‌توان گفت دقیقاً «در ۱۱۲۰ صفحه به حالت سلول ۱m رسیده‌ایم» (ترتیب سلول‌ها/پیل‌های page کامکنی است)؛ ادعای محکم این است که در هر ترکیبِ سلولی با بیش از ۱۱۲۰ صفحهٔ تجمیعی، گزارش ۱۰۰٪ در حالی‌ست که تا پایان راه مانده — همان‌چیزی که probe نشان داد.

**حکم و دلیل:** **تأیید** (هر سه ادعا). شدت مستقل = S2 هم‌راستای ممیز: نه نقض لجر/هویت است و نه اثر مستقیم بر trade (این Phase 1 بوت‌استرپ تحقیقاتی است، نه مصوبی در مسیر اجرا)؛ اما داشبورد بهره‌بردار (وضعیت در Telegram و `--status` در run_apex) گزارشِ گمراه‌کننده می‌دهد و می‌تواند بر تصمیم‌های بهره‌برداری (انتظار «چقدر مانده»، برنامهٔ دستکاری شبانه، نجابتِ سیاست NIGHTLY در W.9 گام‌های بعدی) اثر بگذارد — در راستای تعریف S2 در CALIBRATION.md. بخش «۱۰۰٪ برای runner تازه» از دید من هم‌خانوادهٔ عیب نیست، همان عیب است (همان گیت `pages_fetched > 0` که معکوسش را پنهان می‌کند).

**علت ریشه‌ای:** «len(cells) × 8» در بازنویسی CP-2 به‌عنوان تقریب کفّیِ بوت‌استرپِ deep (≈۷ هفته) برای ده نماد × چهارده تایم‌فریم طراحی شد و در runner فریز منجمد ماند؛ هیچ شمارنده‌ای به تعداد سلول‌های تکمیل‌شده یا به «صفحات واقعی لازم تا امروز برای هر سلول» متصل نشده است. دو علت دامن‌زننده: (۱) progress فقط جمع صفحات fetch‌شده را می‌شمرد و پایان سلول‌ها (به checkpoint) گره نخورد؛ (۲) ETA فقط از `started_at`ِ command("start") سرعت می‌خواند و از checkpointهای این‌بار resume چیزی به estimated-pace اضافه نمی‌کند — این مقررات در کد مستند نیست.

**اثر مستقیم:** خطای سیستماتیک در هر سطحی که `runner.progress()["percent_complete"]` بدون reinterpretation عرضه می‌شود: `_status` در `run_apex.py:577–604`، `status_text()` در service و اعلان‌های Telegram مربوط. نتیجهٔ عملی برای مالک: «۹۵٪ تمام است» به‌معنای واقعی «۹۵ درصدِ سقف مصنوعی ۸×N صفحه گذشته است» است — در ریزترین تایم‌فریم‌ها ممکن است کمتر از یک‌ششمِ راه واقعی سپری شده باشد.

**اثرات ثانویه و تعاملات:** بالادست: ترکیب/تعداد سلول‌ها (محیط فعلی = ۱۴۰) — اگر لیست تغییر کند بدون بازنگری سقف، خطا باز هم بدتر/بهتر می‌شود. پایین‌دست: هیچ اثر مستقیمی بر دادهٔ برداشت‌شده در SQLite (rows همان‌اند) و هیچ اثر مستقیمی بر اجرای بعد از Phase 1؛ اثر ثانویه روان‌شناسی/بهره‌برداری است: اعتماد به «٪» برای تصمیم‌های شبانه، برآوردهای نادرست برای CP-10 به بعد اگر به متن‌های status اعتماد شود. تعامل با K-020: اگر سلول خالی نیز بتواند COMPLETE شود، حتی پس از اصلاح فرمول باید «بر اساس سلول‌های کامل‌شده در checkpoint» حساب کنیم نه بر اساس صفحات.

**نسبت با قرارداد و تصمیم‌ها:** `APEX_GEN5.md` در W.3/W.7 گزارش‌دهی بهره‌برداری را الزام گرفته اما برای صحت عددی «درصد/ETA» متن normative مستقیم ندارد. معیار من برای حکم این بود: «هر گزارش مبتنی‌بر باید نمایانگر مبنای خود باشد» — و امروز این‌طور نیست (به‌خصوص ۱۰۰٪ برای runner تازه). در DECISION_LOG هم تصمیم اسمی برای نرمال‌کردن تخمین صفحات ثبت نشده (D50/… تنها مسائل trade را پوشش می‌دهد). خود ETA در نبود start درست `NO_MEASUREMENT_YET` می‌دهد و این رفتار با منظور طراحی سازگار است؛ مشکل درصد است نه ETA.

**فریز و راه‌حل بیرون از فریز:** علت اصلی در توابع فریز `progress/eta` در `apex/research/bootstrap.py` است. دو مسیر بیرون‌از‌فریز: (الف) در `bootstrap_service.py`، یک wrapper که خروجی runner را با `len(completed)/len(cells)` (از checkpoint) غنی‌سازی و legend صادق «cells-based vs runner-pages» در وضعیت‌ها بگذارد — می‌تواند فوراً در CP-10… اعمال شود؛ (ب) در لایهٔ `run_apex.py:577–604`، نمایش با notation مشخص («raw_runner_pages=…») برای انسجام گزارش CLI.

**گزینه‌های اصلاح:**
- الف) (با حکم مالک): اصلاح فریز به محاسبات مبتنی‌بر سلول‌کامل (‍`completed_cells / cells`) + تخمین صفحات لازم واقعی از DEEP_START تا now به‌ازای هر TF؛ ساده‌ترین root fix ولی contract گزارش‌دهی و تست‌های فعلی پین‌کننده را می‌شکند.
- ب) (خارج از فریز، فوری): در `bootstrap_service.py` (و در صورت نیاز `_status`) نمایش cell-based در اولویت و runner-pages به‌صورت شفاف‌نامه با legend؛ تست‌های فعلی runner سبز می‌مانند.
- پ) هر دو: ب الآن، الف در پنجرهٔ مالک.

**پیشنهاد من:** اکنون ب — شفاف‌سازی در service (غیرفریز) به‌همراه legend — و در پنجرهٔ حکم مالک، الف برای یکدست‌سازی root. هر تصمیم نهایی باید در DECISION_LOG با نام «progress-basis» ثبت شود.

**آزمون پذیرش و رگرسیون:** پذیرش پس از اصلاح: (۱) runner تازه ⇒ خروجی به‌کاربر «۰٪ (fresh)» نه ۱۰۰٪؛ (۲) در میانهٔ deep harvest با صفحات تجمیعی بالا اما سلول‌های تکمیل‌نشده، عدد نمایش‌داده‌شده معطوف به `completed/cells` باشد (با legend نه خام جایگزین)؛ (۳) بدون start، `measured=False/NO_MEASUREMENT_YET` حفظ شود. رگرسیون: `python3 -m pytest -q -p no:cacheprovider tests/unit/test_research_bootstrap.py tests/unit/test_ops_bootstrap_service.py` (پس از گزینهٔ ب همین‌ها باید سبز بمانند) + تست service جدید که سه حالت fresh/mid/complete را روی متنِ نهایی (با legend) چک کند.

---

### C-014 — پس از resume، بازبینی سلامت (recheck) بلافاصله اعمال نمی‌شود

**ادعای ممیز (نقل کوتاه):** «contract می‌گوید پس از وقفهٔ بیش از ۲۴ ساعت، قبل از resume باید health check روی دادهٔ دانلودشده انجام شود، اما `command("resume")` فقط یک فلگ `health_recheck.required=True` برمی‌گرداند و `paused_at` را بلافاصله پاک می‌کند؛ هیچ persist، هیچ گیت در run_phase1 و هیچ recheck واقعی در مسیر resume وجود ندارد. تست فعلی فقط همان فلگ را می‌سنجد» (`apex/research/bootstrap.py`؛ `apex/ops/bootstrap_service.py:1259–1285`؛ `tests/unit/test_research_bootstrap.py:146–157`؛ شدت S2؛ «= G-005»؛ breadcrumb D55).

**آنچه خواندم:**
- `apex/research/bootstrap.py:374–404` (command + `health_recheck_required`): هنگام resume پس از وقفهٔ بیش‌از ۲۴h، در verdict کلید `health_recheck = {'required': True, 'paused_hours': …, 'threshold_hours': 24.0}` گذاشته می‌شود و **در همان فراخوان** `paused=False` و `paused_at=None` می‌شود — سندِ باقی‌مانده از «لازم بود recheck» صفر می‌شود؛ بلافاصله بعد `health_recheck_required()` جواب می‌دهد `{'required': False, 'reason': 'NO_PAUSE_RECORDED'}`. هیچ دادهٔ ماندگاری (DB/state) از نیاز به recheck باقی نمی‌ماند.
- `run_phase1` (246–346) هیچ گیتی برای recheck ندارد: در هر سلول pending، fetch ادامه می‌یابد، فارغ از این که verdictِ resume «required» بوده یا نه.
- `apex/ops/bootstrap_service.py:1259–1285` (غیرفریز): `command` متن را به runner می‌سپارد و خروجی verdict را فقط از طریق `_command_line` به‌صورت متن (شامل «health_recheck=…») گزارش می‌کند؛ هیچ اقدام enforceکننده (مکث، درخواست تأیید، یا قرار دادن gate جلوی run بعدی) رخ نمی‌دهد.
- تست unit در بازهٔ استناد (`tests/unit/test_research_bootstrap.py:146–157`): فقط `verdict["health_recheck"]["required"]` را assert می‌کند؛ هیچ آزمونی برای «پاک‌شدن paused_at»، «پایان‌یافتن مستقیم run پس از resume» یا اجرای recheck نیست — دقیقاً همان‌طور که ممیز گفت.

**بازتولید:** `python3 AUDIT/probes_V1c/C-014.py` (خروجی خام `AUDIT/probes_V1c/C-014.out`; fetcher شمارنده‌دار بدون شبکه):
- pause در epoch واقعی، سپس +۲۵h ⇒ `health_recheck_required() = {'required': True, 'paused_hours': 25.0, 'threshold_hours': 24.0}` (سازگار با contract).
- `command("resume")` → `accepted=True, health_recheck={'required': True, ...}`؛ بلافاصله بعد: `health_recheck_required() = {'required': False, 'reason': 'NO_PAUSE_RECORDED'}` و `state.paused=False, paused_at=None` — همان‌طور که ممیز گفت، فلگ advisory است و مدرک پاک می‌شود.
- `run_phase1` بلافاصله پس از resume: **`status=COMPLETE` با ۲ فراخوانی fetch واقعی** — هیچ recheck، هیچ توقف، هیچ الزام به عمل قبل از restart برداشت.
- `CLAIM_REPRODUCED=True`.

**حکم و دلیل:** **تأیید**. شدت مستقل = S2 هم‌راستای ممیز: نه نقض لجر/هویت است و نه اثر مستقیم بر مسیر trade (این Phase 1 bootstrap تحقیقاتی است)؛ اما یک حکم بهره‌برداری صریح در contract (W.8-3) است که عملاً به «اشاره‌کردن و رد شدن» سقوط کرده و به گزارش متنیِ مالک محدود مانده — وقفهٔ طولانی بدون recheck وارد برداشتِ بالقوه stale می‌شود و بدون persistِ «لازم بود»، تحلیل بعدی دشوار است. در راستای تعریف S2 در CALIBRATION.md.

**علت ریشه‌ای:** در contract حکم ثبت شده اما lifecycle «resume فقط وقتی معتبر است که recheck انجام شده» مهندسی نشده: (۱) `paused_at` بی‌درنگ پاک می‌شود و ردپای «لازم بود» از بین می‌رود؛ (۲) `health_recheck` در ریشهٔ فرمان‌ها (start/pause/resume/stop) نتیجهٔ *اعلامی* است نه *مهار رفتاری*؛ (۳) service — تنها پیام‌رسان مالک — فقط متن گزارش می‌سازد و رفتار را تغییر نمی‌دهد؛ (۴) D55 صراحتاً وضع advisory را توصیه کرده و هدفش «حفاظت از مسیر» بوده، ولی در عمل دیگر هیچ چیزی (نه فریز نه wiring) از انجام‌نشدن recheck جلوگیری نمی‌کند.

**اثر مستقیم:** هر resume پس از گپ >۲۴h بدون هیچ اقدام واسط وارد مسیر برداشت ادامه‌دار روی دادهٔ بالقوه stale می‌شود؛ سیگنال «باید recheck» فقط در یک پیام متنی ممکن است به مالک برسد (و آن هم به wiring واقعی gateway↔service بستگی دارد — همان موضوعی که با G-005 نام‌گذاری شده و در این نشست فقط اشاره می‌شود).

**اثرات ثانویه و تعاملات:** بالادست: مسیر زندهٔ control (telegram/toobit ↔ service) که خود دامنهٔ G-005 است. پایین‌دست: کیفیت داده‌ای که در آموزش‌های بعدی (E11 و فراتر) مصرف می‌شود می‌تواند به‌صورت خانوادگی از batches stale تأثیر بپذیرد؛ این معضل به trade execution (Paper/Ledger) منتقل نمی‌شود اما به «دستاورد بوت‌استرپ» لطمه می‌زند. تعامل با K-020: وقتی empty-page → COMPLETE هم ممکن است، در مدلی که recheck می‌خواهد باز هم verifier نداریم — هر دو به‌خانوادهٔ «health نامطمئن در harvest» برمی‌گردند.

**نسبت با قرارداد و تصمیم‌ها:** `APEX_GEN5.md:17316` (W.8-3): «After pause duration exceeds 24 hours, before resume, re-run health check on downloaded data (detect stale feeds, re-sync as needed).» حق با ممیز است: (۱) «before resume» صریح است و پیاده‌سازی فعلی عملاً «اعلام و عبور» می‌کند؛ (۲) contract نمی‌گوید کدام duty باید recheck را اجرا کند (runner، service، یا اپراتور) — از این رو که تصمیم‌گیری در D55 به advisory برگشت، وجود خود این تناقض بین W.8-3 و D55 بخشی از ریشه است؛ (۳) D55 با اثرِ محضِ پاک‌شدن `paused_at` (که من در probe دیدم) از نظر عملی case را از advisory به «بدون اثر» می‌برد و این در روح تصمیم هم نیست. تطبیق معنادار W.8-3 در وضع فعلی اجرایی نیست.

**فریز و راه‌حل بیرون از فریز:** علت اصلی در `apex/research/bootstrap.py` (فریز). راه‌حل بیرون‌از‌فریز در `BootstrapService` (غیرفریز) ممکن است: (الف) service در `command` پس از دیدن verdict «recheck_required» یک state جانبی (در `bootstrap_state` SQLite یا فایل کنار state) ثبت کند و تا وقتی «تأیید مالک» یا «اتمام recheck» نیامده، فراخوانی بعدی `run` را با status «PENDING_RECHECK» fail-closed پاسخ دهد؛ (ب) پیام صریح به مالک («این resume بدون recheck انجام شد؛ برای اعتبار، فلان فرمان را بزن») که put-out در همان متن service قابل پیاده‌سازی است. محدودیت: اگر فریز عوض نشود، resumeهای مستقیم runner اصلاً تحت این gate نیستند و باید مستند شوند.

**گزینه‌های اصلاح:**
- الف) (با حکم مالک): در فریز، resume را مشروط به `ack_health_recheck=True` (یا فرمان جداگانهٔ «resume_confirm») کنید؛ حکم W.8-3 از advisory به required ارتقا می‌یابد و کد تغییر می‌کند اما قرارداد درست‌تر می‌شود.
- ب) (خارج از فریز، fail-closed): در service، state «needs_recheck_since» پایدار کنید؛ آن‌را فقط در دو راه پاک کنید: (۱) اتمام صریح یک job healthcheck، (۲) تأیید متنی مالک. run تا پاک‌شدن state اجازهٔ شروع Phase 1 ندارد.
- پ) هر دو.

**پیشنهاد من:** اکنون ب (fail-closed در `bootstrap_service.py`، بدون لمس فریز، با storage سبک مشترک) + ثبت در DECISION_LOG که «W.8-3 در عمل required است»، و در پنجرهٔ حکم مالک گزینهٔ الف برای یکپارچگی runner.

**آزمون پذیرش و رگرسیون:** پذیرش پس از اصلاح: (۱) resume پس از وقفهٔ ۲۵h در service مستقیماً به fetch منتهی نشود (fail-closed با PENDING_RECHECK یا معادل)؛ (۲) پاک‌شدن فوراً `paused_at` باعث نشود state «needs_recheck» از دست برود — آن باید در service پایدار بماند و با یکی از دو مسیر پاک شود؛ (۳) بدون تأیید/recheck، run بعدی هیچ فراخوانی fetch انجام ندهد (`fetch_calls==0`). رگرسیون: `python3 -m pytest -q -p no:cacheprovider tests/unit/test_research_bootstrap.py tests/unit/test_ops_bootstrap_service.py` (تست‌های فعلی فریز زیر گزینهٔ ب نباید تغییر کنند؛ پس از حکم مالک، آزمون advisor-f در unit‌ها بازنویسی می‌شود) + تست service جدید برای سناریوی resume→run blocked → confirm → run resumes.
### O-006 — محدودیت شواهد: بودجهٔ پیش‌فرض ۴ معامله و تک‌جفتی family/playbook نیازمند توافق دامنه‌اند

**ادعای ممیز (نقل کوتاه):** «بودجهٔ پیش‌فرض ۴ معامله در cycle وجود دارد و D51 معنای آن را مصوب کرده است؛ family/playbook فعلی هم یک جفت مشخص است. صرف وجود محدودیت را bug اعلام نمی‌کنیم؛ «تمام قابلیت‌ها» باید در برابر دامنهٔ مصوب تعریف شود» (`apex/ops/paper_loop.py:366,527–538`؛ `params/setup_weights_v1.yaml:4–5`؛ `PHASE2_HANDOFF_CP9.md:934–935`؛ ردهٔ S4 / کنترل با دامنهٔ محدود — ردیف نقص نیست، ردیف توافق دامنه است).

**آنچه خواندم:**
- `apex/ops/paper_loop.py:360–370` (امضای ctor: `max_trades_per_cycle: int = 4` دقیقاً در خط 366) و `:527–538` (`_take_budget`/`_release_budget`: بررسی و افزایش سنکرون — رزرو اتمیک زیر semaphore هم‌روندی ۴؛ «`self.trades` is history only and is never a gate»؛ release فقط وقتی submission از پروسه خارج نشود).
- `params/setup_weights_v1.yaml` (فایل کامل): خط ۴ `family_id: SF_FVG_SWEEP_REV` و خط ۵ `playbook_id: PB_FVG_SWEEP_REV_A` — سرلوحهٔ فایل صراحتاً می‌گوید «the only Wave-In family، و FROZEN_BOOTSTRAP — do not retune in code».
- `PHASE2_HANDOFF_CP9.md:935` (WHAT LANDED): «- D51: `max_trades_per_cycle` resets every cycle, is reserved only when a valid plan exists, and is released if the submission does not leave the process. A planless cell does not consume a slot.» — معنای بودجه مصوب ثبت‌شده است (استناد ممیز به خط 934 هم درست است: تیتر D50 در 933، متن D51 از 934–935).
- تست رفرنس D51 در `tests/unit/test_cp146.py:402–445` (`test_d51_six_cycles_each_admit_one_trade`: با cap=1 هر ۶ چرخه دقیقاً یک trade پذیرفته می‌شود و رزرو هر چرخه ریست می‌شود).

**بازتولید:** `python3 AUDIT/probes_V1c/O-006.py` (خروجی خام `AUDIT/probes_V1c/O-006.out`؛ نمونهٔ زندهٔ PaperRuntime با stack واقعی store/ledger/bus در SQLite موقت، بدون شبکه):
- (۱) امضای واقعی ctor: `default max_trades_per_cycle = 4`؛ نمونهٔ زنده: نگهداری بودجه ۴؛ پنج `_take_budget()` متوالی → `[True, True, True, True, False]`؛ پس از یک `_release_budget()` گرفتن بعدی → `True` (رزرو/آزادسازی سنکرون D51).
- (۲) خطوط ۴–۵ فایل params دقیقاً همان دو کلید‌اند و لودر خود مخزن (`apex.config._load_yaml("setup_weights")`) همان جفت `SF_FVG_SWEEP_REV / PB_FVG_SWEEP_REV_A` را برمی‌گرداند.
- (۳) متن D51 در هندآف CP9 در خط 935 یافت شد و به `max_trades_per_cycle` اشاره دارد.
- `CLAIMS_REPRODUCED=True`.

**حکم و دلیل:** **تأیید (به معنای راستی‌آزمایی شواهد)**. ردیف ادعای نقص ندارد — ممیز صراحتاً اعلام می‌کند وجود محدودیت bug نیست و نقش ردیف «تثبیت معیار پذیرش» است. هر سه پایهٔ شاهد ممیز بازتولید شد و شمار خطوط استناد دقیق است. شدت مستقل: مطابق ممیز **S4 / غیرنقص (نیاز بررسی دامنه)** روی مقیاس من — چون عیبی در رفتار کد مشاهده نشد که به S0–S3 منتسب شود.

**علت ریشه‌ای (چرا چنین ردیفی لازم شد):** سرمایه‌گذاری قبلی روی عبارت «بعد از Phase 1 همهٔ قابلیت‌ها را ندارید» (`APEX_GEN5.md:17294` — در بخش C-009 هم نقل شد) و بودجهٔ ایمن D51 می‌توانند توسط یک ارزیاب سطحی به‌عنوان «نقص در تعداد/تنوع معاملات» خوانده شوند؛ درحالی‌که هر دو تصمیم آگاهانهٔ مصوب‌اند (دامنهٔ W قسمت دوم: «After Phase 1 the operator does not have 100% of capabilities …» و D51 در هندآف CP9).

**اثر مستقیم:** هیچ — خود ممیز هم هیچ اثر عدم اصلاحی را «ابهام در معیار پذیرش و انتظار تعداد/تنوع معاملات» معرفی کرده، نه رفتار معیوب سیستم.

**اثرات ثانویه و تعاملات:** حذف عجولانهٔ cap یا جایگزینی family/playbook بدون حکم مالک، کنترل ریسک D51 و معنای آموزش/ارزیابی را تغییر می‌دهد (اثر ثانویهٔ نامبردهٔ خود ممیز). تعامل با C-015 (نشت بودجه در مسیر exception) و C-007 (کیفیت متریک trades) در خانوادهٔ «معنای بودجه/شمارش» قرار می‌گیرد — این سه باید با هم در یک سند دامنه قفل شوند.

**نسبت با قرارداد و تصمیم‌ها:** D51 مصوب است (HANDOFF_CP9:935)؛ جفت family/playbook «FROZEN_BOOTSTRAP» در params است (هر تغییری = تغییر نسخهٔ پارامتر با پروسهٔ خودش، نه patch کد). معیار صحت: اگر پذیرش PAPER روی حذف محدودیت ایمن سوار شود، آن تغییر به‌تناقض با D51 می‌افتد — درست مثل هشدار ممیز.

**فریز و راه‌حل:** نه درایو فریز در این ردیف هست و نه نیازی به تغییر کد. پارامترهای yaml نسخه‌دار و در دستهٔ FROZEN_BOOTSTRAP محسوب می‌شوند (تغییر فقط از مسیر حکم مالک + نسخهٔ جدید yaml).

**گزینه‌های اقدام (همه غیرتهاجمی):**
- الف) **تثبیت سند دامنه (پیشنهاد من):** در DECISION_LOG یا سند پذیرش، فهرست صریح «محدودیت‌های مصوب فعلی» درج شود: cap پیش‌فرض ۴ trade/cycle (D51)، تک‌جفت SF_FVG_SWEEP_REV / PB_FVG_SWEEP_REV_A (params FROZEN_BOOTSTRAP)، و تعریف پذیرش‌پذیر «تمام قابلیت‌ها» در برابر همین دامنه. هزینه: فقط سندی.
- ب) تست پین‌کنندهٔ unit برای دو واقعیت (default=4 در signature و جفت family/playbook از لودر config) — غیرتهاجمی، جلوی رگرسیون سندی را می‌گیرد (probe فعلی دقیقاً همین را می‌کند و می‌تواند مستقیم به تست تبدیل شود).
- پ) اگر مالک دامنه‌ی متفاوت می‌خواهد (cap متفاوت/خانوادهٔ دوم): فقط از مسیر رسمی تصمیم (D-xx جدید + نسخهٔ جدید params) — هرگز با حذف cap یا دور زدن frozen params.

**پیشنهاد من:** الف + ب (سند دامنه + تست پین). بدون تغییر رفتار.

**آزمون پذیرش و رگرسیون:** پذیرش = نبود ابهام: هر گزارش پذیرش PAPER جدید باید با فهرست محدودیت‌های مصوب سازگار باشد و نسخهٔ سند نقل شود. رگرسیون: `python3 -m pytest -q -p no:cacheprovider tests/unit/test_cp146.py tests/integration/test_ops_paper_loop.py` + تبدیل probe O-006 به تست واحد پایدار.

---

### V-003 — اتصال engine→decision در مسیر serve واقعاً برقرار است (کنترل تأییدشده با دامنهٔ محدود)

**ادعای ممیز (نقل کوتاه):** «برخلاف docstring قدیمی DECLARED_SKIP، مسیر serve واقعاً producer.prepare و get_bridge_context را به PaperPlanBridge وصل می‌کند؛ bridge فراخوانی forecast/setup/risk/build_trade_plan دارد. لذا از نام skip نمی‌توان نتیجه گرفت موتور→تصمیم کاملاً اسکلت است. درستی مدل/فرمول و اجرای واقعی دستگاه هنوز تأیید نشده» (`scripts/run_apex.py:748–765`؛ `apex/ops/paper_loop.py:1008–1027`؛ `apex/ops/plan_bridge.py:530–559,774–785,794–817,949–976`؛ `apex/ops/engine_context.py:1798–1841,2283–2335`؛ ردهٔ S4 / کنترل تأییدشده؛ = D-001/D-002، E-016، H-007).

**آنچه خواندم:**
- `scripts/run_apex.py:744–770` (خوانش دقیق): در `_serve`، `producer = EC.EngineContextProducer(...)` (فقط برای PAPER)، آنگاه `plan_bridge = PB.PaperPlanBridge(store=..., environment=..., context_source=producer.get_bridge_context, context_preparer=producer.prepare)` و بلافاصله `PL.PaperRuntime(..., plan_provider=plan_bridge, ...)`. کامنت مجاور صریح است: «every PAPER cell now asks the governed store/context → pattern/setup → gates → forecast → risk/decision chain for a real plan».
- `apex/ops/paper_loop.py:1000–1027` (خوانش دقیق): `run_cycle` پیش از ساخت تسک‌های سلول، `prepare = getattr(self.plan_provider, "prepare", None)` را به‌ازای هر سلول due — **خارج از بودجهٔ trade** — صدا می‌زند؛ آمار `cells_checked/cells_prepared/failures` در `cycle["context_preparation"]` و شکست‌ها در `_context_preparation_failed[cell_id]` با reason ثبت می‌شوند (skip برای `_catch_up_failed`).
- `apex/ops/plan_bridge.py:1–1026` (نقاط کلیدی): ثابت‌های `REQUIRED_CONTEXT_KEYS` (۵۱–۱۰۷) و `REQUIRED_RISK_KEYS` (۱۱۴–۱۳۹)؛ `PaperPlanBridge.prepare` (۵۳۰–۵۴۰ — بیرون از بودجه، PAPER-only، «Never call the plan builder here»)؛ `__call__` (۵۴۲–۵۵۹ + catch در ۵۶۰–۵۸۰ — ردّ نام‌دار نرم در `self.refusals[key]`)؛ `_build` (۶۱۷–۹۷۶): زنجیرهٔ کامل اعتبارسنجی (flatten→required 38-field→e11 shapes→events→_fabric_ref→EvidenceFabric.assemble×۲→disagreement/quality_asymmetry/stale_fraction→resolve conflict→build_context + solvency→pattern_entity→ForecastEvent)، سپس فراخوانی‌ها: `build_forecast` (۷۷۴)، `evaluate_cell` یعنی خانواده + ۱۳ گیت (۷۹۴)، ردّ SETUP_NOT_EMITTED (۸۱۸)، `instantiate_playbook` + `build_stops` (۸۳۷)، `eligibility` (۸۴۹)، `generate_candidates/rank/select` (۸۷۸–۸۸۰)، `arbitrate` (۹۰۳)، `build_proposal` (۹۱۲)، بررسی کامل‌بودن ۲۳ کلید risk (۹۲۱–۹۲۳) + transport-ایمن (۹۲۸–۹۴۲) سپس `adjudicate` (۹۴۸) و `build_trade_plan` (۹۴۹)، و در پایان `_materialize_setup` + ثبت trace در `self.traces`.
- `apex/ops/engine_context.py:1798–1841` (`prepare` با caching بر اساس `input_fingerprint` + `validate_produced_context` + persist به عنوان BRIDGE_CONTEXT fact؛ `get_bridge_context` — docstring: «Exactly 38 context fields / 23 risk fields; no fixture fallback»، کپی ارزان داخل بودجهٔ scheduler، lazy prepare برای فراخوان مستقل) و `:2283–2335` (`prepare_engine_bundle`: محاسبهٔ native کامل — classifier artifact sha256 مقید، تحمل window engine/quality، lineage روی eventها، persist evidence) — خود محاسبات را در این نشست اجرا نکردم (دامنهٔ ردیف «اتصال» است، نه «صحت محاسبات»).
- docstringهای DECLARED_SKIP در `paper_loop.py:501–526` (`_stage_features`/`_stage_engines`): زمان‌گیر قدیمی برای «این increment خود engine evidence تولید نمی‌کند» و «seam فریز SL-5→SL-6» — مسیر فعلی serve با plan_provider واقعی از کنار پرش می‌کند، اما کلمهٔ SKIP به‌تنهایی گمراه‌کننده است (نکتهٔ ممیز).
- تست‌های موجود: `tests/unit/test_plan_bridge.py` (۱۳۸ خط — شکل کاننیکال context برای ردّها؛ از همان برای fixture probe استفاده شد) و تمایز refusal نام‌دار از promotion خام evidence.

**بازتولید:** `python3 AUDIT/probes_V1c/V-003.py` (خروجی خام `AUDIT/probes_V1c/V-003.out`; stack واقعی SQLite/ledger/bus، بدون شبکه؛ **صداقت روش:** در بخش D بدنهٔ ۱۲ تابع مرحله با خروجی‌های canned جایگذاری شد تا ترتیب/وجود فراخوانی‌ها قابل مشاهده باشد؛ تمام کدهای اعتبارسنجی، fabric، conflict، context و risk-completenessِ bridge واقعاً اجرا شدند — هیچ محاسبهٔ مدل بازنویسی نشد):
- A1: runtime با SpyProvider → `prepare_calls=[('BTCUSDT','1h')]` و `context_preparation={'cells_checked':1,'cells_prepared':1,'failures':[]}` با بودجهٔ صفر پیش و پس از چرخه ⇒ نقل ممیز از «prepare بیرون از بودجه» درست است.
- A2: با provider شکست‌خورده → `failures=[{'cell':'BTCUSDT:1h','reason':'ENGINE_CONTEXT_INVALID',...}]` و همان در `_context_preparation_failed` ⇒ ثبت fail-closed per-cell درست است.
- B: `prepare` با preparer واقعی-جاسوسی → فراخوان منتقل شد و `build_trade_plan` هرگز صدا نشد (spy=0)؛ LIVE → استثنای `PAPER_ONLY_EXECUTION`؛ خارج از جهان → ردّ نرم `CELL_OUT_OF_UNIVERSE` در `refusals`؛ بدون context → ردّ نرم `ENGINE_CONTEXT_UNAVAILABLE` (رفتار واقعی `__call__`: استثنا نمی‌اندازد — refusal نام‌دار در dict ثبت و None برمی‌گردد؛ این را probe صادقانه سند کرد چون انتظار اولیهٔ من raise بود و نبود).
- C: `REQUIRED_CONTEXT_KEYS=38` و `REQUIRED_RISK_KEYS=23` — دقیقاً مطابق docstring سرویس‌دهندهٔ engine_context.
- D: با context در شکل کاننیکال تست واحد، `bridge._build` مسیر اعتبارسنجی واقعی را تا انتها پیمود (fabric assemble/resolve/conflict/context سازی شدند — بدون لمس این لایه‌ها exec شد) و توالی فراخوانی‌ها دقیقاً این بود: `build_forecast → evaluate_cell → instantiate_playbook → build_stops → eligibility → generate_candidates → rank → select → arbitrate → build_proposal → adjudicate → build_trade_plan`؛ `_materialize_setup` دقیقاً یک‌بار با `(pattern_id='PAT-WYC-001', regime='TREND')`؛ plan ساخته و trace ثبت شد.
- `CLAIMS_REPRODUCED=True`.

**حکم و دلیل:** **تأیید** (هر سه ستون ادعا: wiring در serve، فراخوانی prepare از runtime، و وجود فراخوانی forecast/setup/risk/plan در bridge). شدت مستقل: **S4 / کنترل تأییدشده** — ادعای نقصی در این ردیف نیست که به S0–S3 برسد. دو قید صداقت همان‌جور که ممیز نوشت: (۱) صحت خود محاسبات producer/engine در این نشست سنجیده نشده (وابسته به شواهد E-016/H-007 و اجرای واقعی روی دادهٔ دستگاه)؛ (۲) probe بخش D ترتیب فراخوانی را اثبات می‌کند نه صحت خروجی مدل را.

**علت ریشه‌ای (چرا ردیف لازم شد):** نام‌گذاری تاریخی DECLARED_SKIP در `_stage_features/_stage_engines` (paper_loop.py:501–526) دربارهٔ «این increment engine evidence تولید نمی‌کند / seam فریز» بود و خوانندهٔ سطحی آن را «موتور→تصمیم اسکلت» برداشت می‌کرد؛ درحالی‌که مسیر آمادهٔ production (serve) جدا از آن docstringها plan_provider واقعی را تزریق می‌کند. شکاف سندی، نه شکاف کدی.

**اثر مستقیم:** آنچه ممیز گفت: از بازنویسی بی‌دلیل producer و از پذیرش بیش‌ازحد آمادگی PAPER هر دو جلوگیری می‌کند؛ موانع D-001/C-002 دست‌نخورده برقرارند (در محدودهٔ این نشست، اتصالِ وجودی تأیید شد — هیچ حکم آمادگی تجاری از آن نمی‌آید).

**اثرات ثانویه و تعاملات:** بالادست: C-002 (ریشهٔ context/bundle که در V1a با S0 تأیید شد) همچنان مانع اجرای end-to-end واقعی است — اتصال V-003 بالای آن مانع سوار است و فقط با رفع آن، شاهد نهایی (E-016) قابل گرفتن است. پایین‌دست: هر تست پذیرش آینده باید latency آماده‌سازی را از `cycle["context_preparation"]` بخواند (در حال حاضر مرئی است — خوب). تعامل با O-006 (دامنهٔ مصوب) و ردیف‌های M-011/M-012 (ستون‌های durable setup) — هم‌پوشانی موضوعی، بدون تناقض.

**نسبت با قرارداد و تصمیم‌ها:** معیار قضاوت ممیز «وجود اتصال کد» بود و آن محقق است؛ قرارداد مصوب مرتبط: D63/D59 (در کد bridge نقل‌قول‌دار رعایت شده‌اند — مثلاً window حکومتی YAML playbook در build_stops/eligibility و ردّ DECISION_NO_TRADE از arbitrate). تصمیم مؤخری در DECISION_LOG که این اتصال را عقب ببرد ندیدم.

**فریز و راه‌حل:** این ردیف درخواست اصلاح کد ندارد. دو اقدام غیرتهاجمی پیشنهادی: (الف) هم‌ترازسازی سند: docstringهای DECLARED_SKIP در paper_loop.py:501–526 با یک جملهٔ «مسیر production را ببین: scripts/run_apex.py:748–765» تصریح شوند تا خوانندهٔ آینده از واژهٔ SKIP نتیجهٔ اسکلت‌بودن نگیرد (تغییر سندی در فایل غیرفریز)؛ (ب) تبدیل probe به تست واحد دائمی (افزودنی، غیرتهاجمی) که wiring A/B/C/D را پین کند تا رگرسیون آتی سریع دیده شود.

**پیشنهاد من:** ب (تست پین دائمی) + الف (یک خط تصریح سندی). کد فعلی را دست نزنید؛ شاهد محاسباتی را در ردیف اختصاصی E-016 بعد از C-002 بگیرید، همان‌طور که ممیز هم خواسته.

**آزمون پذیرش و رگرسیون:** پذیرش تغییرات سندی/تستی: تست جدید چهار بخش را (A1/A2/B/C/D) در CI سبز نگه دارد و docstringها خواننده را به محل wiring ارجاع دهند. رگرسیون: `python3 -m pytest -q -p no:cacheprovider tests/unit/test_plan_bridge.py tests/unit/test_cp146.py tests/integration/test_ops_paper_loop.py` + تست یکپارچهٔ پس از نخستین plan واقعی (E-016) وقتی C-002 رفع شود؛ «اتصال تنها PASS نیست» — همان‌طور که ممیز نوشت.
