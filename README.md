Advanced Biometric Forensic Audit 🛡️⌚

Analyzing Autonomic Nervous System stress and recovery through Fitbit CEDA and HRV sensor data using R and Python.

Project Overview

This repository contains an end-to-end data science pipeline designed to extract "high-resolution" biometric data from Fitbit's export architecture. While standard fitness apps focus on steps and calories, this project performs a Forensic Audit of the raw sensor streams—specifically Continuous Electrodermal Activity (CEDA) and Heart Rate Variability (HRV)—to evaluate the neurological cost of exercise.

Key Features

Data Consolidation (Python/Pandas): A robust script to merge 130+ fragmented CSV/JSON files into a unified master database.

Forensic Auditing: Identifying sensor "dropouts" and mechanical noise artifacts during high-intensity lifting.

Interactive Visualizations (R/Plotly): Dynamic reports mapping sympathetic arousal (fight-or-flight) against cardiovascular strain.

Recovery Tracking: Utilizing RMSSD (Root Mean Square of Successive Differences) to monitor parasympathetic recovery 24/7.

Interactive Reports

The analysis is split into two primary modules:

Activity Analysis: General overview of daily movement and "Step Gaps."

Technical Deep-Dive: Forensic audit of CEDA, HRV, and sensor integrity.

Tech Stack

Languages: R (Tidyverse), Python (Pandas)

Interactivity: Plotly, R Markdown

Data Source: Fitbit Personal Data Export (Raw)

Environment: Google Colab (ETL), RStudio (Analysis)

Created by BT — March 2026
