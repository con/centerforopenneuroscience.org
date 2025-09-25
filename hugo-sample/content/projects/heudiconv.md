---
title: "HeuDiConv / ReproIn"
project_types: ["own"]
status: "active"
website: "https://github.com/nipy/heudiconv"
description: "Flexible DICOM converter for organizing brain imaging data into structured directory layouts"
---

[HeuDiConv](https://github.com/nipy/heudiconv) is a flexible DICOM converter for organizing brain imaging data into structured directory layouts. As a part of the larger, NIH supported [ReproNim](http://repronim.org) effort, we are developing a HeuDiConv-based [ReproIn](http://reproin.repronim.org) solution for turnkey automatic conversion of all collected MR data to a collection of the BIDS DataLad datasets. It includes a flexible BIDS-like specification how to name scanning sequences in the scanner, and a [HeuDiConv reproin.py heuristic](https://github.com/nipy/heudiconv/blob/master/heudiconv/heuristics/reproin.py) to automate layout and conversion of the datasets. This solution is deployed at [DBIC (Dartmouth Brain Imaging Center)](https://www.dartmouth.edu/dbic/), it already facilitates reproducible research, data sharing, and uploads to central archives such as NDA.

## Publications

- Halchenko et al., (2024). HeuDiConv — flexible DICOM conversion into structured directory layouts. Journal of Open Source Software, 9(99), 5839 [DOI: 10.21105/joss.05839](https://joss.theoj.org/papers/10.21105/joss.05839).
- [M. Visconti di Oleggio Castello](/whoweare#matteo_visconti_di_oleggio_castello_), James E. Dobson, Terry Sackett, Chandana Kodiweera, [J.V. Haxby](/whoweare#james_v_haxby_), M. Goncalves, S. Ghosh, [Y.O. Halchenko](/whoweare#yaroslav_o_halchenko_) [ReproIn: automatic generation of shareable, version-controlled BIDS datasets from MR scanners](http://goo.gl/Z3soj7), OHBM 2018, Singapore.