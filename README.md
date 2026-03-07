# Advanced Biometric Forensic Audit 🛡️⌚

Analyzing Autonomic Nervous System stress and recovery through Fitbit CEDA and HRV sensor data using R and Python.

## View the Live Project
[Click here to view the interactive HTML dashboard](https://taberbrian.github.io/fitbit-biometric-forensic-audit/)

## Project Overview

This repository contains an end-to-end data science pipeline designed to extract "high-resolution" biometric data from Fitbit's export architecture. While standard fitness apps focus on steps and calories, this project performs a Forensic Audit of the raw sensor streams—specifically Continuous Electrodermal Activity (CEDA) and Heart Rate Variability (HRV)—to evaluate the neurological cost of exercise.

Data Source & Acknowledgments

Original Data: All raw biometric data was sourced from a Fitbit Personal Data Export (JSON/CSV dump). This project utilizes the "Body Response," "Heart Rate," and "Activity" telemetry streams.

Preprocessing: The initial data consolidation and cleaning were performed in Google Colab using Python. Special recognition is given to the Fitbit engineering community for documenting the schema of the body_response sensor logs.

Methodology: The ETL Pipeline

The transformation of 130+ fragmented files into a single master database involved a three-stage process:

Extraction (Python): Iterating through multi-nested directory structures to find sensor-specific CSV and JSON files.

Transformation (Python/Pandas): * Standardizing disparate Unix and ISO timestamps to America/Chicago local time.

Downsampling high-frequency sensor pings to minute-by-minute averages.

Left-merging 10 distinct biometric streams onto a continuous timeline.

Analysis (R/Tidyverse): Performing statistical audits and generating interactive Plotly visualizations in R Markdown.

Interactive Reports

The analysis is split into two primary modules:

Activity Analysis: General overview of daily movement and "Step Gaps."

Technical Deep-Dive: Forensic audit of CEDA, HRV, and sensor integrity.

Tech Stack

Languages: R (Tidyverse), Python (Pandas)

Interactivity: Plotly, R Markdown, HTML/Tailwind (Dashboard)

Environment: Google Colab (ETL), RStudio (Analysis)

Created by BT — March 2026
