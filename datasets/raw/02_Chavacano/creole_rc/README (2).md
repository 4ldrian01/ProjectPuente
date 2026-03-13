
---
license: cc-by-sa-4.0
language: 
- cbk
pretty_name: Creole Rc
task_categories: 
- relation-extraction
tags: 
- relation-extraction
---

CreoleRC is a subset created by the CreoleVal paper. Relation classification (RC) aims to identify semantic associations between entities within a text, essential for applications like knowledge base completion and question answering. The dataset is sourced from Wikipedia and manually annotated. CreoleRC contains 5 creoles, but SEACrowd is interested specifically in the Chavacano subset.


## Languages

cbk

## Supported Tasks

Relation Extraction

## Dataset Usage
### Using `datasets` library
```
from datasets import load_dataset
dset = datasets.load_dataset("SEACrowd/creole_rc", trust_remote_code=True)
```
### Using `seacrowd` library
```import seacrowd as sc
# Load the dataset using the default config
dset = sc.load_dataset("creole_rc", schema="seacrowd")
# Check all available subsets (config names) of the dataset
print(sc.available_config_names("creole_rc"))
# Load the dataset using a specific config
dset = sc.load_dataset_by_config_name(config_name="<config_name>")
```

More details on how to load the `seacrowd` library can be found [here](https://github.com/SEACrowd/seacrowd-datahub?tab=readme-ov-file#how-to-use).


## Dataset Homepage

[https://github.com/hclent/CreoleVal/tree/main/nlu/relation_classification](https://github.com/hclent/CreoleVal/tree/main/nlu/relation_classification)

## Dataset Version

Source: 1.0.0. SEACrowd: 2024.06.20.

## Dataset License

Creative Commons Attribution Share Alike 4.0 (cc-by-sa-4.0)

## Citation

If you are using the **Creole Rc** dataloader in your work, please cite the following:
```
@misc{lent2023creoleval,
    title={CreoleVal: Multilingual Multitask Benchmarks for Creoles},
    author={Heather Lent and Kushal Tatariya and Raj Dabre and Yiyi Chen and Marcell Fekete and Esther Ploeger and Li Zhou and Hans Erik Heje and Diptesh Kanojia and Paul Belony and Marcel Bollmann and     Loïc Grobol and Miryam de Lhoneux and Daniel Hershcovich and Michel DeGraff and Anders Søgaard and Johannes Bjerva},
    year={2023},
    eprint={2310.19567},
    archivePrefix={arXiv},
    primaryClass={cs.CL}
}


@article{lovenia2024seacrowd,
    title={SEACrowd: A Multilingual Multimodal Data Hub and Benchmark Suite for Southeast Asian Languages}, 
    author={Holy Lovenia and Rahmad Mahendra and Salsabil Maulana Akbar and Lester James V. Miranda and Jennifer Santoso and Elyanah Aco and Akhdan Fadhilah and Jonibek Mansurov and Joseph Marvin Imperial and Onno P. Kampman and Joel Ruben Antony Moniz and Muhammad Ravi Shulthan Habibi and Frederikus Hudi and Railey Montalan and Ryan Ignatius and Joanito Agili Lopo and William Nixon and Börje F. Karlsson and James Jaya and Ryandito Diandaru and Yuze Gao and Patrick Amadeus and Bin Wang and Jan Christian Blaise Cruz and Chenxi Whitehouse and Ivan Halim Parmonangan and Maria Khelli and Wenyu Zhang and Lucky Susanto and Reynard Adha Ryanda and Sonny Lazuardi Hermawan and Dan John Velasco and Muhammad Dehan Al Kautsar and Willy Fitra Hendria and Yasmin Moslem and Noah Flynn and Muhammad Farid Adilazuarda and Haochen Li and Johanes Lee and R. Damanhuri and Shuo Sun and Muhammad Reza Qorib and Amirbek Djanibekov and Wei Qi Leong and Quyet V. Do and Niklas Muennighoff and Tanrada Pansuwan and Ilham Firdausi Putra and Yan Xu and Ngee Chia Tai and Ayu Purwarianti and Sebastian Ruder and William Tjhi and Peerat Limkonchotiwat and Alham Fikri Aji and Sedrick Keh and Genta Indra Winata and Ruochen Zhang and Fajri Koto and Zheng-Xin Yong and Samuel Cahyawijaya},
    year={2024},
    eprint={2406.10118},
    journal={arXiv preprint arXiv: 2406.10118}
}

```