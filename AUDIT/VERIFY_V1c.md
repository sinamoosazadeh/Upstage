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
| C-009 | _در حال بررسی_ | S1 | — | — | — | — |
| C-011 | _در حال بررسی_ | S2 | — | — | K-020 | — |
| C-014 | _در حال بررسی_ | S2 | — | — | G-005، K-020 | — |
| C-015 | تأیید | S2 | S2 | نه | C-005, D51 (HANDOFF_CP9:934) | الف (release در مسیر exception اثباتاً-پیش‌ارسال + علت‌ثبت) |
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









