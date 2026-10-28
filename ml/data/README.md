# ml/data — UNSW-NB15 dataset files (git-ignored)

The dataset is **not** stored in Git. Download it yourself and place the files here.
`.gitignore` excludes everything in this directory except this README.

## 1. Download from the official source

1. Open the official page: https://research.unsw.edu.au/projects/unsw-nb15-dataset
2. Follow its download link to the UNSW-hosted folder and open the **CSV Files** folder.
3. Download the files below. The two partitioned files are in the sub-folder for the
   training and testing sets.

| File | Needed for | Notes |
|---|---|---|
| `UNSW_NB15_training-set.csv` | **Required** — training and validation | Has a header row |
| `UNSW_NB15_testing-set.csv` | **Required** — final test evaluation | Has a header row |
| `UNSW-NB15_1.csv` … `UNSW-NB15_4.csv` | Optional — uploads with IP addresses, ports, timestamps | No header row; several hundred MB in total |
| `NUSW-NB15_features.csv` | Optional — column names for the four files above | Used to verify the expected column order |

The dataset is published by UNSW Canberra for research use; cite it in the project report:

- N. Moustafa and J. Slay, "UNSW-NB15: a comprehensive data set for network intrusion
  detection systems (UNSW-NB15 network data set)," *Military Communications and Information
  Systems Conference (MilCIS)*, 2015.
- N. Moustafa and J. Slay, "The evaluation of Network Anomaly Detection Systems: Statistical
  analysis of the UNSW-NB15 data set and the comparison with the KDD99 data set,"
  *Information Security Journal: A Global Perspective*, 2016.

Do not use unofficial copies: they may be altered, and results from them cannot be traced.

## 2. Place the files

```
ml/data/
├── README.md
├── UNSW_NB15_training-set.csv
├── UNSW_NB15_testing-set.csv
├── UNSW-NB15_1.csv            (optional)
├── UNSW-NB15_2.csv            (optional)
├── UNSW-NB15_3.csv            (optional)
├── UNSW-NB15_4.csv            (optional)
└── NUSW-NB15_features.csv     (optional)
```

File-name matching ignores upper/lower case. Do not edit the files: their SHA-256 hashes are
recorded in every report so results can be traced to the exact data.

## 3. Check them

```bash
cd ml
sentinel-ml profile
```

This writes `ml/reports/data_profile.md` with the real columns, types, blank values, label
distributions, duplicates, train/test overlap, and IP availability. It stops with a clear
error if a file is missing or its columns differ from what the code expects.

## Synthetic data

Tests generate small **synthetic** files in temporary directories, together with a marker
file named `SYNTHETIC_DATA_NOT_UNSW_NB15`. Any report produced from such a directory carries a
"SYNTHETIC DATA" banner. Never place the marker file next to the real dataset.
