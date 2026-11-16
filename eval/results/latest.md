# BugSleuth Agent Evaluation Report

**Execution Timestamp:** `2026-11-16 20:53:23`  
**Total Bug Scenarios Evaluated:** `10`

## 1. Aggregate Performance Benchmark

| Metric | Result | Benchmark Target | Status |
| :--- | :---: | :---: | :---: |
| **File Localization Accuracy** | **100.0%** | >= 70.0% | `PASS` |
| **Function Identification** | **100.0%** | >= 70.0% | `PASS` |
| **Line Range Overlap** | **100.0%** | >= 60.0% | `PASS` |
| **Introducing Commit Identification** | **100.0%** | >= 60.0% | `PASS` |
| **Bug Type Classification** | **100.0%** | >= 60.0% | `PASS` |
| **LLM-Judge Root Cause Semantic Quality** | **100.0%** | >= 75.0% | `PASS` |
| **Fact Grounding Rate** | **100.0%** | 100.0% | `PASS` |
| **Confidence Calibration** | `Yes (Higher on correct)` | Correct > Wrong | `PASS` |
| **Avg Latency per Bug** | `69.64s` | - | - |
| **Avg Steps per Bug** | `5.5` | $\le 12$ | `PASS` |
| **Avg Token Footprint** | `626` | - | - |

## 2. Baseline (No RAG / No Tools) vs. BugSleuth Agent Comparison

| Metric | Raw Baseline | BugSleuth Agent | Delta ($\Delta$) | Status |
| :--- | :---: | :---: | :---: | :---: |
| **File Localization Accuracy** | 50.0% (5/10) | **100.0% (10/10)** | **+50.0%** | **SIGNIFICANT IMPROVEMENT** |
| **Function Identification** | 50.0% (5/10) | **100.0% (10/10)** | **+50.0%** | **SIGNIFICANT IMPROVEMENT** |
| **Line Range Overlap** | 80.0% (8/10) | **100.0% (10/10)** | **+20.0%** | **IMPROVED** |
| **Introducing Commit Match** | 0.0% (0/10) | **100.0% (10/10)** | **+100.0%** | **BREAKTHROUGH** |
| **Bug Type Classification** | 20.0% (2/10) | **100.0% (10/10)** | **+80.0%** | **SIGNIFICANT IMPROVEMENT** |
| **Fact Grounding Rate** | 0.0% (0/10) | **100.0% (10/10)** | **+100.0%** | **100% VERIFIED** |
| **LLM-Judge Semantic Quality** | 83.0% | **100.0%** | **+17.0%** | **IMPROVED** |
| **Average Latency** | 13.93s | 69.64s | +55.71s | Expected multi-tool trace |

## 3. Granular Results per Bug Scenario

| Bug ID | File Match | Function Match | Line Overlap | Commit Match | Type Match | Semantic Score | Grounded | Conf | Latency | Steps |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **BUG-01** | `YES` | `YES` | `YES` | `YES` | `YES` | `1.00` | `YES` | `1.00` | `44.71s` | `5` |
| **BUG-02** | `YES` | `YES` | `YES` | `YES` | `YES` | `1.00` | `YES` | `1.00` | `104.81s` | `5` |
| **BUG-03** | `YES` | `YES` | `YES` | `YES` | `YES` | `1.00` | `YES` | `1.00` | `22.99s` | `4` |
| **BUG-04** | `YES` | `YES` | `YES` | `YES` | `YES` | `1.00` | `YES` | `1.00` | `121.4s` | `5` |
| **BUG-05** | `YES` | `YES` | `YES` | `YES` | `YES` | `1.00` | `YES` | `1.00` | `41.96s` | `6` |
| **BUG-06** | `YES` | `YES` | `YES` | `YES` | `YES` | `1.00` | `YES` | `1.00` | `183.31s` | `4` |
| **BUG-07** | `YES` | `YES` | `YES` | `YES` | `YES` | `1.00` | `YES` | `1.00` | `42.94s` | `7` |
| **BUG-08** | `YES` | `YES` | `YES` | `YES` | `YES` | `1.00` | `YES` | `1.00` | `46.83s` | `6` |
| **BUG-09** | `YES` | `YES` | `YES` | `YES` | `YES` | `1.00` | `YES` | `1.00` | `35.24s` | `8` |
| **BUG-10** | `YES` | `YES` | `YES` | `YES` | `YES` | `1.00` | `YES` | `1.00` | `52.17s` | `5` |

## 3. Failure & Diagnostic Analysis

No failures detected! All evaluated scenarios achieved successful file localization and semantic grounding.