# BugSleuth Baseline Evaluation (No RAG / No Tools)

**Execution Timestamp:** `2026-11-16 20:39:51`  
**Total Bug Scenarios Evaluated:** `10`

## 1. Aggregate Performance Benchmark

| Metric | Result | Benchmark Target | Status |
| :--- | :---: | :---: | :---: |
| **File Localization Accuracy** | **50.0%** | $\ge 70.0\%$ | `NEEDS IMPROVEMENT` |
| **Function Identification** | **50.0%** | $\ge 70.0\%$ | `WARN` |
| **Line Range Overlap** | **80.0%** | $\ge 60.0\%$ | `PASS` |
| **Introducing Commit Identification** | **0.0%** | $\ge 60.0\%$ | `WARN` |
| **Bug Type Classification** | **20.0%** | $\ge 60.0\%$ | `WARN` |
| **LLM-Judge Root Cause Semantic Quality** | **83.0%** | $\ge 75.0\%$ | `PASS` |
| **Fact Grounding Rate** | **0.0%** | $100.0\%$ | `WARN` |
| **Confidence Calibration** | `Yes (Higher on correct)` | Correct > Wrong | `PASS` |
| **Avg Latency per Bug** | `13.93s` | - | - |
| **Avg Steps per Bug** | `1.0` | $\le 12$ | `PASS` |
| **Avg Token Footprint** | `260` | - | - |

## 2. Granular Results per Bug Scenario

| Bug ID | File Match | Function Match | Line Overlap | Commit Match | Type Match | Semantic Score | Grounded | Conf | Latency | Steps |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **BUG-01** | `YES` | `YES` | `YES` | `NO` | `YES` | `0.50` | `NO` | `1.00` | `7.68s` | `1` |
| **BUG-02** | `YES` | `YES` | `NO` | `NO` | `NO` | `0.50` | `NO` | `0.80` | `50.8s` | `1` |
| **BUG-03** | `NO` | `NO` | `YES` | `NO` | `YES` | `1.00` | `NO` | `0.95` | `29.0s` | `1` |
| **BUG-04** | `YES` | `YES` | `YES` | `NO` | `NO` | `1.00` | `NO` | `1.00` | `3.27s` | `1` |
| **BUG-05** | `YES` | `YES` | `YES` | `NO` | `NO` | `1.00` | `NO` | `0.95` | `2.89s` | `1` |
| **BUG-06** | `YES` | `YES` | `YES` | `NO` | `NO` | `1.00` | `NO` | `0.95` | `7.2s` | `1` |
| **BUG-07** | `NO` | `NO` | `YES` | `NO` | `NO` | `0.80` | `NO` | `0.80` | `3.55s` | `1` |
| **BUG-08** | `NO` | `NO` | `NO` | `NO` | `NO` | `0.50` | `NO` | `0.50` | `11.77s` | `1` |
| **BUG-09** | `NO` | `NO` | `YES` | `NO` | `NO` | `1.00` | `NO` | `0.80` | `10.74s` | `1` |
| **BUG-10** | `NO` | `NO` | `YES` | `NO` | `NO` | `1.00` | `NO` | `0.80` | `12.41s` | `1` |

## 3. Failure & Diagnostic Analysis

### BUG-01
- **Reported Location:** `shopapp/users.py::get_user_notification_preference`
- **File Match:** `True` | **Commit Match:** `False`
- **Semantic Score:** `0.50`
- **Judge Justification:** The agent identified a missing null check on an object leading to a TypeError, but wrongly targeted the user object being None rather than the preferences dictionary being None during dictionary indexing.

### BUG-02
- **Reported Location:** `shopapp/discounts.py::calculate_bulk_discount`
- **File Match:** `True` | **Commit Match:** `False`
- **Semantic Score:** `0.50`
- **Judge Justification:** The agent correctly identified the resulting symptom (skipping the 20% discount bracket for quantities like 25), but omitted the exact code-level mechanism (the off-by-one error in range(len(tiers) - 1)).

### BUG-03
- **Reported Location:** `shopapp/scenarios.py::reserve_stock`
- **File Match:** `False` | **Commit Match:** `False`
- **Semantic Score:** `1.00`
- **Judge Justification:** The agent accurately and precisely identified the flawed comparison operator and its exact impact on boundary conditions matching the ground truth.

### BUG-04
- **Reported Location:** `shopapp/cart.py::apply_coupon_to_cart`
- **File Match:** `True` | **Commit Match:** `False`
- **Semantic Score:** `1.00`
- **Judge Justification:** The agent accurately identified the exact root cause mechanism, noting that the coupon lookup returns None and the code fails to check for this before calling .get() on it.

### BUG-05
- **Reported Location:** `shopapp/payments.py::calculate_payment_breakdown`
- **File Match:** `True` | **Commit Match:** `False`
- **Semantic Score:** `1.00`
- **Judge Justification:** The agent accurately identified floating-point arithmetic without proper decimal rounding on fractional amounts as the exact root cause.

### BUG-06
- **Reported Location:** `shopapp/orders.py::assemble_order_items`
- **File Match:** `True` | **Commit Match:** `False`
- **Semantic Score:** `1.00`
- **Judge Justification:** The agent accurately identified the exact root cause mechanism, noting the improper key access of item['item_id'] leading to a KeyError in order assembly.

### BUG-07
- **Reported Location:** `shopapp/scenarios.py::Default channels`
- **File Match:** `False` | **Commit Match:** `False`
- **Semantic Score:** `0.80`
- **Judge Justification:** The agent correctly identified the core mechanism of mutable default arguments causing state retention across invocations, though it unnecessarily expanded the scope to class or module-level definitions.

### BUG-08
- **Reported Location:** `shopapp/scenarios.py::reproduce_bug_08`
- **File Match:** `False` | **Commit Match:** `False`
- **Semantic Score:** `0.50`
- **Judge Justification:** The agent identified the symptom of dropped records and a false success status, but missed the specific root cause mechanism of the overbroad try-except block masking the exception.

### BUG-09
- **Reported Location:** `shopapp/warehouse/cache.py::reserve_stock`
- **File Match:** `False` | **Commit Match:** `False`
- **Semantic Score:** `1.00`
- **Judge Justification:** The agent accurately identified that the warehouse cache layer is not being invalidated when stock units are reserved, perfectly matching the ground truth.

### BUG-10
- **Reported Location:** `shopapp/gateways.py::convert_to_cents`
- **File Match:** `False` | **Commit Match:** `False`
- **Semantic Score:** `1.00`
- **Judge Justification:** The agent accurately identified the exact root cause mechanism where dollars are divided by 100 instead of multiplied when converting to cents.
