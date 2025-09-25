---
title: "SuperEEG"
project_types: ["own"]
status: "active"
website: "https://supereeg.readthedocs.io/en/latest/"
description: "Python toolbox for inferring whole-brain activity from sparse ECoG recordings"
logo: "/theme/img/3rd/supereeg_logo.png"
---

[SuperEEG](https://supereeg.readthedocs.io/en/latest/) is a Python toolbox for inferring whole-brain activity from sparse ECoG recordings. The way the technique works is to leverage data from different patients' brains (who had electrodes implanted in different locations) to learn a "correlation model" that describes how activity patterns at different locations throughout the brain relate. Given this model, along with data from a sparse set of locations, we use Gaussian process regression to "fill in" what the patients' brains were "most probably" doing when those recordings were taken. Details on our approach may be found in [this preprint](https://www.biorxiv.org/content/early/2018/10/12/121020). You may also be interested in watching [this talk](https://www.youtube.com/watch?v=t6snLszEneA&feature=youtu.be&t=35) or reading this [blog post](https://community.sfn.org/t/supereeg-ecog-data-breaks-free-from-electrodes/8344) from a recent conference.

## Publications

- L.L.W. Owen, A.C. Heusser, and [J.R. Manning](/whoweare#jeremy_rothman_manning_) (2018). [A Gaussian process model of human electrocorticographic data](https://www.biorxiv.org/content/early/2018/10/12/121020). bioRxiv, 121020.