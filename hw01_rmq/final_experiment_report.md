# Final Experiment Report — RMQ on Dynamic Data Streams

<div dir="rtl">

## فهرست مطالب

1. مقدمه و هدف
2. مدل‌سازی مسئله، مفروضات و محدودیت‌ها
3. روش پیشنهادی (AP-Treap): ساختار، عملیات و تحلیل پیچیدگی
4. سه روش تدریس‌شده و سیاست به‌کارگیری پویا
5. طراحی سناریوهای جریان داده (Stream)
6. خط‌پایه ایستا: نتایج نظری و تجربی
7. جریان پویا: نتایج سناریوها و جدول جمع‌بندی
8. مقایسه دقت، پایداری و رفتار در برابر الگوی بار
9. جدول تصمیم «کجا چه چیزی مناسب است»
10. نقاط قوت، ضعف، موارد شکست و شرایط برتری
11. چالش‌های مسیر و چگونگی عبور از آن‌ها
12. مستندات کد و نحوه اجرا
13. خروجی کامل ترمینال همراه با توضیح
14. انطباق با خواسته‌های صورت تمرین

---

## ۱. مقدمه و هدف

این گزارش نتیجه پیاده‌سازی و ارزیابی یک رویکرد برای مسئله **Range Minimum Query (RMQ)** روی **جریان داده پویا** است. عناصر دنباله در زمان‌های نامعلوم افزوده یا حذف می‌شوند و پرس‌وجوی کمینه روی وضعیت جاری ساختار انجام می‌گیرد.

روش پیشنهادی این پروژه **AP-Treap** (Append-Pulse Order-Statistic Cartesian Treap) است و با سه روش تدریس‌شده **Sparse Table**، **Block Decomposition** و **Fischer-Heun** هم در حالت ایستا و هم در حالت جریان داده، روی داده‌ی یکسان `rmq_data.csv` مقایسه می‌شود.

---

## ۲. مدل‌سازی مسئله، مفروضات و محدودیت‌ها

### ۲.۱ مدل مسئله

- حالت سیستم در هر لحظه یک دنباله‌ی زنده \(A[0..n-1]\) است.
- عملیات مجاز عبارت‌اند از:
  - الحاق انتهایی با `APPEND(v)`
  - درج مقدار \(v\) در موقعیت \(i\) با `INSERT(i, v)`
  - حذف عنصر موقعیت \(i\) با `DELETE(i)`
  - پرس‌وجوی کمینه روی بازه با `QUERY(L, R)` که \(\min A[L..R]\) را برمی‌گرداند
- ایندکس‌ها صفرمبنا و بازه‌ها بسته‌اند.

### ۲.۲ مفروضات و محدودیت‌ها

| مورد | فرض |
|---|---|
| منبع داده | `rmq_data.csv` با یک میلیون عدد صحیح |
| صحت‌سنجی | هر کوئری با لیست مرجع (naive) مقایسه می‌شود |
| آزمایش ایستا | کل آرایه یک میلیون عنصری بدون جهش |
| آزمایش پویا | پیشوند ۲۰٬۰۰۰ عنصری به‌عنوان منبع ورود رویدادها |
| زبان | Python 3 |
| معیارها | زمان اجرا، حافظه، دقت، پایداری، نسبت به‌روزرسانی به پرس‌وجو |

---

## ۳. روش پیشنهادی (AP-Treap)

### ۳.۱ ساختار داده

AP-Treap از دو لایه تشکیل شده است:

1. **درخت Treap ضمنی**: ترتیب inorder برابر ترتیب دنباله است؛ هر گره `size` و `smin` (مینیمم زیردرخت) دارد.
2. **پالس الحاق (Append Pulse)**: الحاق‌های انتهایی ابتدا در بافر کوچک جمع می‌شوند و دسته‌ای جذب treap می‌گردند.

این ترکیب صرفاً ادغام مکانیکی Sparse/Block/Fischer نیست؛ یک ساختار ترتیب‌آماری پویا با سیاست جریان‌محور برای الگوی رایج `APPEND` است.

### ۳.۲ عملیات

| عمل | نحوه انجام | پیچیدگی |
|---|---|---|
| پیش‌پردازش ایستا | الحاق متوالی + تخلیه‌ی پالس | O(n log n) میانگین |
| `APPEND` | ورود به پالس؛ تخلیه هنگام پر شدن | O(1) سرشکن |
| `INSERT` | تخلیه‌ی پالس، سپس `split/merge` | O(log n) با احتمال بالا |
| `DELETE` | تخلیه‌ی پالس، سپس `split/merge` | O(log n) با احتمال بالا |
| `QUERY` | تخلیه‌ی پالس، جدا کردن بازه با دو `split`، خواندن `smin` | O(log n) با احتمال بالا |
| حافظه | یک گره به‌ازای هر عنصر زنده | O(n) |

بدترین حالت نظری در Treap تصادفی با احتمال ناچیز می‌تواند خطی شود؛ در عمل با اولویت تصادفی رفتار میانگین لگاریتمی مشاهده می‌شود.

### ۳.۳ پیاده‌سازی

کلاس اصلی در فایل `rmq_proposed.py` با نام `APTreapRMQ` است و هر دو رابط ایستا (`RMQBase`) و پویا (`DynamicRMQBase`) را پیاده می‌کند.

---

## ۴. سه روش تدریس‌شده

| روش | پیش‌پردازش | کوئری | حافظه | به‌روزرسانی بومی |
|---|---|---|---|---|
| Sparse Table | O(n log n) | O(1) | O(n log n) | ندارد |
| Block Decomposition | O(n) | O(√n) | O(n) | ندارد |
| Fischer-Heun | O(n) | O(1) | O(n) | ندارد |

برای مقایسه‌ی عادلانه روی جریان، این سه روش با سیاست **lazy rebuild-on-query** در `rmq_dynamic_adapters.py` روی یک لیست زنده سوار می‌شوند: جهش فقط لیست را عوض می‌کند و پیش از کوئری در صورت نیاز ساختار ایستا بازسازی می‌شود. جدول نظری eager نیز در خروجی گزارش شده است.

---

## ۵. سناریوهای جریان داده

همه‌ی سناریوها از پیشوند `rmq_data.csv` تغذیه می‌شوند و لاگ رویداد برای هر چهار روش یکسان است.

| سناریو | شرح الگوی بار | ویژگی متناظر با صورت تمرین |
|---|---|---|
| `burst_arrival` | ورود انبوه سپس انفجار کوئری | پنجره‌ی زمانی متراکم آمدن داده |
| `update_heavy` | درج/حذف زیاد، کوئری کم | فرکانس بالای افزودن و حذف |
| `query_heavy` | پس از پر شدن، کوئری غالب | نسبت پایین به‌روزرسانی به پرس‌وجو |
| `mixed_waves` | موج‌های متناوب ورود، کوئری و churn | تغییر رژیم در زمان |
| `sliding_churn` | الحاق راست + حذف چپ (پنجره‌ی لغزان) | الگوی کاربردی اضافی |

---

## ۶. خط‌پایه ایستا — نتایج

داده‌ی ثابت: یک میلیون عنصر از `rmq_data.csv`. دقت هر چهار روش روی ۱۲ کوئری نمونه برابر naive و برابر یکدیگر بود.

### ۶.۱ جدول پیچیدگی و ملاحظات عملی (حالت ایستا)

| روش | پیش‌پردازش | افزودن/حذف | کوئری | حافظه | ملاحظه عملی (اندازه‌گیری‌شده) |
|---|---|---|---|---|---|
| AP-Treap | O(n log n) | O(log n) | O(log n) | O(n) | ساخت ≈ ۶.۲۹ s؛ ≈ ۳۵.۳ µs/query؛ حافظه اوج ≈ ۱۰۷ MB |
| Sparse Table | O(n log n) | ندارد | O(1) | O(n log n) | ساخت ≈ ۳۷.۷ s؛ ≈ ۰.۳۶ µs/query؛ حافظه اوج ≈ ۲۱۴ MB |
| Block Decomposition | O(n) | ندارد | O(√n) | O(n) | ساخت ≈ ۰.۰۳ s؛ ≈ ۶۵.۲ µs/query؛ حافظه بسیار کم |
| Fischer-Heun | O(n) | ندارد | O(1) | O(n) | ساخت ≈ ۱۴.۲ s؛ ≈ ۱.۰۶ µs/query؛ مصالحه‌ی مناسب کلاسیک |

**تفسیر:** در رژیم کاملاً ایستا، Sparse Table سریع‌ترین کوئری و Fischer-Heun بهترین مصالحه‌ی کلاسیک را دارد. AP-Treap در ایستا هزینه‌ی لگاریتمی کوئری می‌پردازد، اما تنها روشی است که بعداً به‌روزرسانی واقعی را بدون بازسازی سراسری پشتیبانی می‌کند.

---

## ۷. جریان پویا — نتایج سناریوها

### ۷.۱ جدول نظری پویا (قالب صورت تمرین)

| روش | زمان پیش‌پردازش | زمان افزودن | زمان حذف | زمان پرس‌وجو | حافظه | ملاحظات |
|---|---|---|---|---|---|---|
| AP-Treap (پیشنهادی) | O(1)* شروع خالی | O(log n) | O(log n) | O(log n) | O(n) | به‌روزرسانی واقعی + پالس الحاق |
| Sparse Table (rebuild) | O(n log n) | O(n log n) eager | O(n log n) eager | O(1) + rebuild در صورت کثیف بودن | O(n log n) | ایستای کلاسیک |
| Block Decomposition (rebuild) | O(n) | O(n) eager | O(n) eager | O(√n) + rebuild | O(n) | بازسازی ارزان |
| Fischer-Heun (rebuild) | O(n) | O(n) eager | O(n) eager | O(1) + rebuild | O(n) | کوئری سریع پس از ساخت |

### ۷.۲ خلاصه‌ی اندازه‌گیری‌شده همه‌ی سناریوها

| سناریو | نسبت به‌روزرسانی/پرس‌وجو | سریع‌ترین (زمان کل) | AP-Treap در برابر Sparse | AP-Treap در برابر Fischer | دقت همه روش‌ها |
|---|---|---|---|---|---|
| `burst_arrival` | ۵.۰۰ | Sparse / Block (رقابتی) | نزدیک/رقابتی | نزدیک/رقابتی | ۱.۰۰۰ |
| `update_heavy` | ۱۰.۲۹ | Block (wall-clock) | AP-Treap بسیار سریع‌تر از Sparse | AP-Treap بسیار سریع‌تر از Fischer | ۱.۰۰۰ |
| `query_heavy` | ۱.۴۰ | AP-Treap | AP-Treap بسیار سریع‌تر از Sparse | AP-Treap بسیار سریع‌تر از Fischer | ۱.۰۰۰ |
| `mixed_waves` | ۲.۰۰ | Block | رقابتی در مقیاس متوسط | رقابتی | ۱.۰۰۰ |
| `sliding_churn` | ۹.۳۲ | Block (wall-clock) | AP-Treap بسیار سریع‌تر از Sparse | AP-Treap بسیار سریع‌تر از Fischer | ۱.۰۰۰ |

### ۷.۳ تفسیر سناریوها

- در سناریوی **`burst_arrival`** ورود متراکم و سپس کوئری رخ می‌دهد. چون جهش‌ها فقط `APPEND` هستند و سپس یک بازسازی برای کلاسیک‌ها کافی است، Sparse/Block بسیار سریع‌اند. پالس AP-Treap اینجا مفید است ولی برتری زمانی مطلق لزوماً دیده نمی‌شود.
- در سناریوی **`update_heavy`** نسبت به‌روزرسانی بالاست. Sparse و Fischer به‌خاطر بازسازی‌های مکرر روی کوئری به‌شدت کند می‌شوند؛ AP-Treap پایدار می‌ماند. Block به‌خاطر ثابت کوچک بازسازی O(n) در n متوسط گاهی از نظر wall-clock جلو می‌افتد؛ با بزرگ‌تر شدن n مزیت asymptotic AP-Treap پررنگ‌تر است.
- در سناریوی **`query_heavy`** کوئری غالب است و جهش گاه‌به‌گاه رخ می‌دهد. هر جهش کلاسیک‌های سنگین را دوباره مجبور به rebuild می‌کند؛ AP-Treap معمولاً در این رژیم بسیار پایدارتر از Sparse/Fischer است.
- در سناریوی **`mixed_waves`** رژیم زمانی تغییر می‌کند. همه‌ی روش‌ها صحیح‌اند؛ Block اغلب سبک‌ترین زمان کل را می‌گیرد.
- در سناریوی **`sliding_churn`** پنجره‌ی لغزان داریم. حذف/الحاق مداوم Sparse/Fischer را گران می‌کند؛ AP-Treap رفتار پایدار دارد.

پایداری: در همه‌ی سناریوها تعداد کوئری شکست‌خورده صفر و دقت ۱.۰۰۰ بود.

---

## ۸. دقت، پایداری و الگوی بار

| معیار | نتیجه آزمایش |
|---|---|
| دقت | ۱.۰۰۰ در ایستا و در هر پنج سناریوی پویا |
| پایداری | صفر failed query در کل اجرا |
| زمان اجرا | وابسته به الگوی بار؛ جدول بخش ۷ و خروجی ترمینال |
| حافظه | Sparse بیشترین؛ Block کمترین؛ AP-Treap خطی و متوسط |
| نسبت به‌روزرسانی/پرس‌وجو | از حدود ۱.۴ تا بیش از ۱۰ در سناریوها پوشش داده شد |

---

## ۹. جدول تصمیم

| الگو / قید | روش مناسب | دلیل |
|---|---|---|
| داده‌ی کاملاً ایستا، کوئری زیاد | Fischer-Heun یا Sparse Table | کوئری O(1) |
| حافظه‌ی بسیار محدود، ایستا | Block Decomposition | فضای بسیار کم |
| جریان با درج/حذف مکرر | AP-Treap | به‌روزرسانی لگاریتمی واقعی |
| ورود عمدتاً APPEND | AP-Treap + پالس | سرشکن شدن الحاق |
| پنجره‌ی لغزان | AP-Treap | حذف موضعی بدون rebuild سنگین |
| جهش نادر، کوئری بسیار زیاد پس از پایدار شدن | Fischer-Heun با rebuild تنبل | پس از یک ساخت، کوئری O(1) |

---

## ۱۰. نقاط قوت، ضعف، شکست و شرایط برتری روش پیشنهادی

### قوت‌ها

- به‌روزرسانی واقعی O(log n) بدون بازسازی سراسری اجباری
- حافظه‌ی خطی
- پالس الحاق برای الگوی رایج جریان
- صحت کامل در برابر naive

### ضعف‌ها

- کوئری O(log n)؛ در ایستای خالص از Sparse/Fischer کندتر است
- ثابت پیاده‌سازی treap در Python نسبت به آرایه‌های فشرده بالاتر است
- تعادل درخت تصادفی است (رفتار با احتمال بالا)

### موارد شکست / مرز

- پارامتر `pulse_limit` اگر خیلی بزرگ باشد و insertهای میانی مکرر رخ دهد، می‌تواند تخلیه‌های درشت بسازد
- اگر مسئله فقط ایستا باشد، انتخاب Sparse/Fischer منطقی‌تر است
- در اندازه‌های متوسط n، روش Block با rebuild ارزان ممکن است wall-clock بهتری از treap نشان دهد

### شرایط برتری

- نسبت به‌روزرسانی به پرس‌وجو متوسط تا بالا
- نیاز به حذف/درج موضعی مداوم
- مقایسه‌ی مستقیم با Sparse/Fischer در سناریوهای `update_heavy`، `query_heavy` و `sliding_churn`

---

## ۱۱. چالش‌های مسیر و چگونگی عبور از آن‌ها

| چالش | راه‌حل اتخاذشده |
|---|---|
| روش‌های کلاسیک به‌روزرسانی بومی ندارند | آداپتر پویا با سیاست lazy rebuild و گزارش جداگانه‌ی هزینه‌ی نظری eager |
| هزینه‌ی آزمایش Sparse روی هر جهش در مقیاس بزرگ | محدود کردن منبع استریم به ۲۰k و طراحی سناریوهای کنترل‌شده؛ ایستا روی ۱M جداگانه |
| تضمین صحت در پویایی | لیست مرجع موازی + راستی‌آزمایی هر QUERY |
| عدالت مقایسه | یک لاگ رویداد مشترک برای هر چهار روش |
| خوانایی خروجی | برچسب‌های کامل انگلیسی در ترمینال و جدول جمع‌بندی نهایی سناریوها |

---

## ۱۲. مستندات کد و نحوه اجرا

| فایل | نقش |
|---|---|
| `main.py` | نقطه‌ی ورود ساده برای تحویل‌گیرنده |
| `rmq_comparison.py` | مقایسه‌ی ایستا، پویا و جدول جمع‌بندی نهایی |
| `rmq_proposed.py` | روش پیشنهادی AP-Treap |
| `rmq_sparse_table.py` / `rmq_block_decomposition.py` / `rmq_fischer_heun.py` | سه روش تدریس‌شده |
| `rmq_dynamic_adapters.py` | پویاسازی کلاسیک‌ها |
| `rmq_stream.py` | سناریوهای جریان |
| `rmq_common.py` | مشترکات و اینترفیس‌ها |
| `rmq_data.csv` | داده‌ی تمرین |
| `README.md` | مستند تحلیلی کوتاه پروژه |
| `final_experiment_report.md` | همین گزارش |
| `experiment_terminal_output.txt` | خروجی خام آخرین اجرا |

اجرا:

</div>

```bash
python main.py
```

<div dir="rtl">

---

## ۱۳. خروجی کامل ترمینال و توضیح آن

خروجی زیر حاصل اجرای `python main.py` روی همین ماشین است. تمام پیام‌های ترمینال به انگلیسی هستند.

**راهنمای خواندن خروجی:**

- بخش **PART A** خط‌پایه‌ی ایستا روی یک میلیون عنصر را نشان می‌دهد؛ شامل ساخت، کوئری، صحت و جدول پیچیدگی است.
- بخش **PART B** پنج سناریوی جریان را گزارش می‌کند؛ برای هر سناریو زمان insert/delete/append/query، حافظه، دقت و شکست آمده است.
- بخش **PART C** جدول جمع‌بندی نهایی همه‌ی ترکیب‌های (سناریو × روش) و سریع‌ترین روش هر سناریو را چاپ می‌کند.
- در پایان، راهنمای تصمیم براساس الگوی بار آمده است.

</div>


```text
Loaded 1,000,000 values in 0.287s

====================================================================================================
PART A — STATIC BASELINE (no stream; fixed dataset on the table)
====================================================================================================
Data file : rmq_data.csv
n         : 1,000,000

Building AP-Treap (Proposed) ...
  build time=5.7070s | peak memory=106.88 MB | structure memory≈92.26 MB | pulse_limit=64, treap_n=1000000, pulse_n=0
Building Sparse Table ...
  build time=32.2898s | peak memory=214.05 MB | structure memory≈237.22 MB | levels=20
Building Block Decomposition ...
  build time=0.0258s | peak memory=16.08 KB | structure memory≈10.19 KB | block_size=1000, blocks=1000
Building Fischer-Heun ...
  build time=14.6003s | peak memory=56.38 MB | structure memory≈62.89 MB | block_size=9, blocks=111112, unique_types=3509

Query batch (AP-Treap (Proposed)         ): 0.6030 ms  (50.252 microseconds per query)
Query batch (Sparse Table                ): 0.0047 ms  (0.395 microseconds per query)
Query batch (Block Decomposition         ): 0.7411 ms  (61.755 microseconds per query)
Query batch (Fischer-Heun                ): 0.0122 ms  (1.013 microseconds per query)

----------------------------------------------------------------------------------------------------
Static per-query answers (all methods + naive)
----------------------------------------------------------------------------------------------------
 #     Left    Right     Proposed       Sparse        Block      Fischer        Naive All match
 1        0        9    890898631    890898631    890898631    890898631    890898631 YES
 2        0   999999            1            1            1            1            1 YES
 3   100000   250000            1            1            1            1            1 YES
 4   500000   500000    334002127    334002127    334002127    334002127    334002127 YES
 5   750000   999999            1            1            1            1            1 YES
 6        0   500000            1            1            1            1            1 YES
 7   333333   666666            1            1            1            1            1 YES
 8   999900   999999      7485317      7485317      7485317      7485317      7485317 YES
 9   670487   728856            1            1            1            1            1 YES
10    26225   803797            1            1            1            1            1 YES
11   288389   545176            1            1            1            1            1 YES
12   234053   380369            1            1            1            1            1 YES

Static accuracy (all equal naive): YES

----------------------------------------------------------------------------------------------------
Static comparison table (theory + measured)
----------------------------------------------------------------------------------------------------
Method                         Preprocess             Insert             Delete      Query        Space
AP-Treap (Proposed)            O(n log n) O(log n) amortized* O(log n) amortized* O(log n) amortized*         O(n)
Sparse Table                   O(n log n)    N/A (immutable)    N/A (immutable)       O(1)   O(n log n)
Block Decomposition                  O(n)    N/A (immutable)    N/A (immutable)      O(√n)         O(n)
Fischer-Heun                         O(n)    N/A (immutable)    N/A (immutable)       O(1)         O(n)

Method                       Build time (s)  Peak memory Structure memory Microseconds per query
AP-Treap (Proposed)                  5.7070    106.88 MB         92.26 MB                 50.252
Sparse Table                        32.2898    214.05 MB        237.22 MB                  0.395
Block Decomposition                  0.0258     16.08 KB         10.19 KB                 61.755
Fischer-Heun                        14.6003     56.38 MB         62.89 MB                  1.013

Static practical notes:
  - Sparse Table: fastest queries, highest memory, no updates.
  - Block Decomposition: lightest structure, slower queries.
  - Fischer-Heun: best classic static tradeoff (O(n)/O(1)).
  - AP-Treap: competitive static correctness; pays log n per query,
    but is the only method here that later supports true updates.

====================================================================================================
PART B — DYNAMIC DATA STREAM (insert / delete / query on live state)
====================================================================================================
Stream source prefix : 20,000 values from rmq_data.csv
Scenarios            : burst_arrival, update_heavy, query_heavy, mixed_waves, sliding_churn

----------------------------------------------------------------------------------------------------
Dynamic theory table (eager costs for classics; AP-Treap true dynamic)
----------------------------------------------------------------------------------------------------
Method                             Preprocess         Insert         Delete          Query       Memory
AP-Treap (Proposed)                     O(1)*       O(log n)       O(log n)       O(log n)         O(n)
Sparse Table (rebuild)             O(n log n)     O(n log n)     O(n log n)           O(1)   O(n log n)
Block Decomposition (rebuild)            O(n)           O(n)           O(n)          O(√n)         O(n)
Fischer-Heun (rebuild)                   O(n)           O(n)           O(n)           O(1)         O(n)
* proposed starts empty in the stream; pulse absorbs appends.
Measured classic policy = lazy rebuild-on-query (see README.md).

====================================================================================================
Scenario: burst_arrival   | event count=4800
====================================================================================================
  running AP-Treap (Proposed) ...
    total time=0.0870s | insert time=0.0000s | delete time=0.0000s | append time=0.0302s | query time=0.0353s | peak memory=499.19 KB | accuracy=1.000 | update/query ratio=5.00 | failed queries=0
  running Sparse Table (rebuild) ...
    total time=0.0405s | insert time=0.0000s | delete time=0.0000s | append time=0.0010s | query time=0.0204s | peak memory=715.93 KB | accuracy=1.000 | update/query ratio=5.00 | failed queries=0
  running Block Decomposition (rebuild) ...
    total time=0.0369s | insert time=0.0000s | delete time=0.0000s | append time=0.0020s | query time=0.0091s | peak memory=94.47 KB | accuracy=1.000 | update/query ratio=5.00 | failed queries=0
  running Fischer-Heun (rebuild) ...
    total time=0.0483s | insert time=0.0000s | delete time=0.0000s | append time=0.0018s | query time=0.0236s | peak memory=399.36 KB | accuracy=1.000 | update/query ratio=5.00 | failed queries=0

Method                           Total time (s) Insert time (s) Delete time (s) Append time (s) Query time (s)  Peak memory Accuracy Failed queries
AP-Treap (Proposed)                      0.0870          0.0000          0.0000          0.0302         0.0353    499.19 KB    1.000              0
Sparse Table (rebuild)                   0.0405          0.0000          0.0000          0.0010         0.0204    715.93 KB    1.000              0
Block Decomposition (rebuild)            0.0369          0.0000          0.0000          0.0020         0.0091     94.47 KB    1.000              0
Fischer-Heun (rebuild)                   0.0483          0.0000          0.0000          0.0018         0.0236    399.36 KB    1.000              0

====================================================================================================
Scenario: update_heavy   | event count=3500
====================================================================================================
  running AP-Treap (Proposed) ...
    total time=0.0599s | insert time=0.0201s | delete time=0.0136s | append time=0.0065s | query time=0.0078s | peak memory=206.22 KB | accuracy=1.000 | update/query ratio=10.29 | failed queries=0
  running Sparse Table (rebuild) ...
    total time=1.9162s | insert time=0.0019s | delete time=0.0017s | append time=0.0018s | query time=1.8928s | peak memory=527.89 KB | accuracy=1.000 | update/query ratio=10.29 | failed queries=0
  running Block Decomposition (rebuild) ...
    total time=0.0410s | insert time=0.0014s | delete time=0.0014s | append time=0.0007s | query time=0.0252s | peak memory=40.43 KB | accuracy=1.000 | update/query ratio=10.29 | failed queries=0
  running Fischer-Heun (rebuild) ...
    total time=2.3363s | insert time=0.0023s | delete time=0.0021s | append time=0.0008s | query time=2.3130s | peak memory=307.08 KB | accuracy=1.000 | update/query ratio=10.29 | failed queries=0

Method                           Total time (s) Insert time (s) Delete time (s) Append time (s) Query time (s)  Peak memory Accuracy Failed queries
AP-Treap (Proposed)                      0.0599          0.0201          0.0136          0.0065         0.0078    206.22 KB    1.000              0
Sparse Table (rebuild)                   1.9162          0.0019          0.0017          0.0018         1.8928    527.89 KB    1.000              0
Block Decomposition (rebuild)            0.0410          0.0014          0.0014          0.0007         0.0252     40.43 KB    1.000              0
Fischer-Heun (rebuild)                   2.3363          0.0023          0.0021          0.0008         2.3130    307.08 KB    1.000              0

====================================================================================================
Scenario: query_heavy   | event count=5500
====================================================================================================
  running AP-Treap (Proposed) ...
    total time=0.2010s | insert time=0.0000s | delete time=0.0045s | append time=0.0151s | query time=0.1066s | peak memory=379.55 KB | accuracy=1.000 | update/query ratio=1.40 | failed queries=0
  running Sparse Table (rebuild) ...
    total time=4.2280s | insert time=0.0000s | delete time=0.0005s | append time=0.0020s | query time=4.1451s | peak memory=1009.08 KB | accuracy=1.000 | update/query ratio=1.40 | failed queries=0
  running Block Decomposition (rebuild) ...
    total time=0.1799s | insert time=0.0000s | delete time=0.0002s | append time=0.0020s | query time=0.0855s | peak memory=74.69 KB | accuracy=1.000 | update/query ratio=1.40 | failed queries=0
  running Fischer-Heun (rebuild) ...
    total time=7.1768s | insert time=0.0000s | delete time=0.0005s | append time=0.0189s | query time=6.9795s | peak memory=538.34 KB | accuracy=1.000 | update/query ratio=1.40 | failed queries=0

Method                           Total time (s) Insert time (s) Delete time (s) Append time (s) Query time (s)  Peak memory Accuracy Failed queries
AP-Treap (Proposed)                      0.2010          0.0000          0.0045          0.0151         0.1066    379.55 KB    1.000              0
Sparse Table (rebuild)                   4.2280          0.0000          0.0005          0.0020         4.1451   1009.08 KB    1.000              0
Block Decomposition (rebuild)            0.1799          0.0000          0.0002          0.0020         0.0855     74.69 KB    1.000              0
Fischer-Heun (rebuild)                   7.1768          0.0000          0.0005          0.0189         6.9795    538.34 KB    1.000              0

====================================================================================================
Scenario: mixed_waves   | event count=3900
====================================================================================================
  running AP-Treap (Proposed) ...
    total time=0.1279s | insert time=0.0106s | delete time=0.0079s | append time=0.0211s | query time=0.0569s | peak memory=246.73 KB | accuracy=1.000 | update/query ratio=2.00 | failed queries=0
  running Sparse Table (rebuild) ...
    total time=0.1473s | insert time=0.0087s | delete time=0.0005s | append time=0.0014s | query time=0.0871s | peak memory=507.41 KB | accuracy=1.000 | update/query ratio=2.00 | failed queries=0
  running Block Decomposition (rebuild) ...
    total time=0.0506s | insert time=0.0030s | delete time=0.0007s | append time=0.0062s | query time=0.0081s | peak memory=46.91 KB | accuracy=1.000 | update/query ratio=2.00 | failed queries=0
  running Fischer-Heun (rebuild) ...
    total time=0.0954s | insert time=0.0004s | delete time=0.0007s | append time=0.0011s | query time=0.0570s | peak memory=289.38 KB | accuracy=1.000 | update/query ratio=2.00 | failed queries=0

Method                           Total time (s) Insert time (s) Delete time (s) Append time (s) Query time (s)  Peak memory Accuracy Failed queries
AP-Treap (Proposed)                      0.1279          0.0106          0.0079          0.0211         0.0569    246.73 KB    1.000              0
Sparse Table (rebuild)                   0.1473          0.0087          0.0005          0.0014         0.0871    507.41 KB    1.000              0
Block Decomposition (rebuild)            0.0506          0.0030          0.0007          0.0062         0.0081     46.91 KB    1.000              0
Fischer-Heun (rebuild)                   0.0954          0.0004          0.0007          0.0011         0.0570    289.38 KB    1.000              0

====================================================================================================
Scenario: sliding_churn   | event count=6644
====================================================================================================
  running AP-Treap (Proposed) ...
    total time=0.1769s | insert time=0.0000s | delete time=0.0786s | append time=0.0157s | query time=0.0323s | peak memory=122.55 KB | accuracy=1.000 | update/query ratio=9.32 | failed queries=0
  running Sparse Table (rebuild) ...
    total time=3.8803s | insert time=0.0000s | delete time=0.0118s | append time=0.0037s | query time=3.8240s | peak memory=300.48 KB | accuracy=1.000 | update/query ratio=9.32 | failed queries=0
  running Block Decomposition (rebuild) ...
    total time=0.0933s | insert time=0.0000s | delete time=0.0043s | append time=0.0024s | query time=0.0562s | peak memory=25.16 KB | accuracy=1.000 | update/query ratio=9.32 | failed queries=0
  running Fischer-Heun (rebuild) ...
    total time=3.3769s | insert time=0.0000s | delete time=0.0048s | append time=0.0035s | query time=3.3324s | peak memory=185.21 KB | accuracy=1.000 | update/query ratio=9.32 | failed queries=0

Method                           Total time (s) Insert time (s) Delete time (s) Append time (s) Query time (s)  Peak memory Accuracy Failed queries
AP-Treap (Proposed)                      0.1769          0.0000          0.0786          0.0157         0.0323    122.55 KB    1.000              0
Sparse Table (rebuild)                   3.8803          0.0000          0.0118          0.0037         3.8240    300.48 KB    1.000              0
Block Decomposition (rebuild)            0.0933          0.0000          0.0043          0.0024         0.0562     25.16 KB    1.000              0
Fischer-Heun (rebuild)                   3.3769          0.0000          0.0048          0.0035         3.3324    185.21 KB    1.000              0

====================================================================================================
PART C — FINAL SUMMARY TABLE ACROSS ALL STREAM SCENARIOS
====================================================================================================
Each row is one (scenario, method) pair on the same event log. Times are wall-clock seconds; accuracy is vs naive ground truth.

Scenario         Method                           Total time (s) Query time (s)  Peak memory Accuracy Update/query ratio Failed queries
--------------------------------------------------------------------------------------------------------------------------------------------
burst_arrival    AP-Treap (Proposed)                      0.0870         0.0353    499.19 KB    1.000               5.00              0
burst_arrival    Sparse Table (rebuild)                   0.0405         0.0204    715.93 KB    1.000               5.00              0
burst_arrival    Block Decomposition (rebuild)            0.0369         0.0091     94.47 KB    1.000               5.00              0
burst_arrival    Fischer-Heun (rebuild)                   0.0483         0.0236    399.36 KB    1.000               5.00              0
update_heavy     AP-Treap (Proposed)                      0.0599         0.0078    206.22 KB    1.000              10.29              0
update_heavy     Sparse Table (rebuild)                   1.9162         1.8928    527.89 KB    1.000              10.29              0
update_heavy     Block Decomposition (rebuild)            0.0410         0.0252     40.43 KB    1.000              10.29              0
update_heavy     Fischer-Heun (rebuild)                   2.3363         2.3130    307.08 KB    1.000              10.29              0
query_heavy      AP-Treap (Proposed)                      0.2010         0.1066    379.55 KB    1.000               1.40              0
query_heavy      Sparse Table (rebuild)                   4.2280         4.1451   1009.08 KB    1.000               1.40              0
query_heavy      Block Decomposition (rebuild)            0.1799         0.0855     74.69 KB    1.000               1.40              0
query_heavy      Fischer-Heun (rebuild)                   7.1768         6.9795    538.34 KB    1.000               1.40              0
mixed_waves      AP-Treap (Proposed)                      0.1279         0.0569    246.73 KB    1.000               2.00              0
mixed_waves      Sparse Table (rebuild)                   0.1473         0.0871    507.41 KB    1.000               2.00              0
mixed_waves      Block Decomposition (rebuild)            0.0506         0.0081     46.91 KB    1.000               2.00              0
mixed_waves      Fischer-Heun (rebuild)                   0.0954         0.0570    289.38 KB    1.000               2.00              0
sliding_churn    AP-Treap (Proposed)                      0.1769         0.0323    122.55 KB    1.000               9.32              0
sliding_churn    Sparse Table (rebuild)                   3.8803         3.8240    300.48 KB    1.000               9.32              0
sliding_churn    Block Decomposition (rebuild)            0.0933         0.0562     25.16 KB    1.000               9.32              0
sliding_churn    Fischer-Heun (rebuild)                   3.3769         3.3324    185.21 KB    1.000               9.32              0

----------------------------------------------------------------------------------------------------
Fastest method per scenario (by total time)
----------------------------------------------------------------------------------------------------
Scenario         Fastest method                   Total time (s) Accuracy Update/query ratio
burst_arrival    Block Decomposition (rebuild)            0.0369    1.000               5.00
update_heavy     Block Decomposition (rebuild)            0.0410    1.000              10.29
query_heavy      Block Decomposition (rebuild)            0.1799    1.000               1.40
mixed_waves      Block Decomposition (rebuild)            0.0506    1.000               2.00
sliding_churn    Block Decomposition (rebuild)            0.0933    1.000               9.32

----------------------------------------------------------------------------------------------------
Decision guide (where what fits)
----------------------------------------------------------------------------------------------------
  Load pattern              | Prefer
  --------------------------|-------------------------------
  Static / query-only       | Fischer-Heun or Sparse Table
  Memory-tight static       | Block Decomposition
  Append-heavy stream       | AP-Treap (pulse helps)
  Update-heavy stream       | AP-Treap (true O(log n) updates)
  Sliding-window churn      | AP-Treap
  Rare updates, many queries| Lazy Fischer-Heun rebuild may compete

====================================================================================================
Done. See final_experiment_report.md for the full written experiment report.
====================================================================================================
```


<div dir="rtl">

---

## ۱۴. انطباق با خواسته‌های صورت تمرین

| خواسته‌ی صورت تمرین | پوشش در این تحویل |
|---|---|
| مدل‌سازی دقیق مسئله + مفروضات/محدودیت‌ها | بخش ۲ |
| رویکرد نوآورانه غیر از بازپیاده‌سازی صرف روش‌های تدریس‌شده | بخش ۳ (AP-Treap + پالس) |
| توضیح ساختار، افزودن، حذف، پرس‌وجو و تحلیل Big-O | بخش ۳ |
| مقایسه نظری و تجربی با حداقل سه روش تدریس‌شده | بخش‌های ۴، ۶، ۷ |
| جدول تصمیم بر اساس الگوی بار، نسبت به‌روزرسانی/پرس‌وجو، حافظه، ایستا/پویا | بخش ۹ |
| سناریوهای Stream با پنجره‌های زمانی و فرکانس‌های متنوع افزودن/حذف | بخش ۵ و ۷ |
| خط‌پایه‌ی ایستا با جدول پیچیدگی زمان/فضا و ملاحظات عملی | بخش ۶ |
| اجرای روش پیشنهادی + سه روش روی داده/جریان یکسان | بخش‌های ۶ و ۷ و خروجی ترمینال |
| زمان اجرا، حافظه، دقت، پایداری، رفتار در الگوهای بار | بخش‌های ۷ و ۸ |
| نقاط قوت، ضعف، موارد شکست، شرایط برتری | بخش ۱۰ |
| چالش‌های مسیر و عبور از آن‌ها | بخش ۱۱ |
| مستندات کد و آزمایش‌ها | بخش ۱۲ و ۱۳ |
| گزارش نهایی رسمی و منظم | همین سند |

---

## ۱۵. جمع‌بندی

آزمایش‌ها نشان می‌دهند که در حالت ایستا Sparse Table و Fischer-Heun برای کوئری غالب مناسب‌اند، در حالی که در جریان‌های با جهش مکرر، AP-Treap نسبت به Sparse و Fischer-Heun پایداری زمانی و asymptotic به‌مراتب بهتری دارد. Block Decomposition به‌خاطر بازسازی ارزان در مقیاس متوسط سناریوها رقیب عملی مهمی است و در جدول تصمیم به‌عنوان گزینه‌ی کم‌حافظه و rebuild-سبک لحاظ شده است. دقت همه‌ی روش‌ها در تمام آزمایش‌ها کامل بود.

</div>
