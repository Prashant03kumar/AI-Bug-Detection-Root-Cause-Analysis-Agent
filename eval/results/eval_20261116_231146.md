# BugSleuth Agent Evaluation Report

**Execution Timestamp:** `2026-11-16 23:11:46`  
**Total Bug Scenarios Evaluated:** `10`

## 1. Aggregate Performance Benchmark

| Metric | Result | Benchmark Target | Status |
| :--- | :---: | :---: | :---: |
| **File Localization Accuracy** | **90.0%** | >= 70.0% | `PASS` |
| **Function Identification** | **90.0%** | >= 70.0% | `PASS` |
| **Line Range Overlap** | **90.0%** | >= 60.0% | `PASS` |
| **Introducing Commit Identification** | **90.0%** | >= 60.0% | `PASS` |
| **Bug Type Classification** | **80.0%** | >= 60.0% | `PASS` |
| **LLM-Judge Root Cause Semantic Quality** | **90.0%** | >= 75.0% | `PASS` |
| **Fact Grounding Rate** | **90.0%** | 100.0% | `WARN` |
| **Confidence Calibration** | `Yes (Higher on correct)` | Correct > Wrong | `PASS` |
| **Avg Latency per Bug** | `248.21s` | - | - |
| **Avg Steps per Bug** | `4.5` | $\le 12$ | `PASS` |
| **Avg Token Footprint** | `607` | - | - |

## 2. Granular Results per Bug Scenario

| Bug ID | File Match | Function Match | Line Overlap | Commit Match | Type Match | Semantic Score | Grounded | Conf | Latency | Steps |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **BUG-01** | `YES` | `YES` | `YES` | `YES` | `NO` | `1.00` | `YES` | `1.00` | `152.01s` | `5` |
| **BUG-02** | `YES` | `YES` | `YES` | `YES` | `YES` | `1.00` | `YES` | `1.00` | `399.12s` | `6` |
| **BUG-03** | `YES` | `YES` | `YES` | `YES` | `YES` | `1.00` | `YES` | `1.00` | `135.11s` | `4` |
| **BUG-04** | `YES` | `YES` | `YES` | `YES` | `YES` | `1.00` | `YES` | `1.00` | `124.79s` | `4` |
| **BUG-05** | `YES` | `YES` | `YES` | `YES` | `YES` | `1.00` | `YES` | `1.00` | `141.21s` | `6` |
| **BUG-06** | `YES` | `YES` | `YES` | `YES` | `YES` | `1.00` | `YES` | `1.00` | `87.9s` | `4` |
| **BUG-07** | `YES` | `YES` | `YES` | `YES` | `YES` | `1.00` | `YES` | `1.00` | `61.09s` | `5` |
| **BUG-08** | `YES` | `YES` | `YES` | `YES` | `YES` | `1.00` | `YES` | `1.00` | `59.4s` | `5` |
| **BUG-09** | `YES` | `YES` | `YES` | `YES` | `YES` | `1.00` | `YES` | `1.00` | `52.23s` | `5` |
| **BUG-10** | `NO` | `NO` | `NO` | `NO` | `NO` | `0.00` | `NO` | `0.10` | `1269.24s` | `1` |

## 3. Failure & Diagnostic Analysis

### BUG-10
- **Reported Location:** `unknown::unknown`
- **File Match:** `False` | **Commit Match:** `False`
- **Semantic Score:** `0.00`
- **Judge Justification:** The agent failed to produce a root cause analysis entirely, reporting an automated synthesis failure instead.
