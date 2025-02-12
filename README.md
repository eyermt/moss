# Map of Open Source Science (MOSS)
MOSS is a project of [OSSci](https://www.opensource.science/), an initiative of [NumFOCUS](https://numfocus.org/).


## Overview

This Map of Open Source Science is a proof of concept right now and as such, nothing is accurate.

This project aims to map open source software and scientific (e.g., peer-reviewed) research via one comprehensive project. This repository houses the backend (e.g., database, API endpoints, etc.) as well as various front-end frameworks (in /frontends) which allow for cool visualizations.

## Running

To start the backend, which is deployed on a production basis at [backend.some-domain-we-need-to-buy.com](backend.some-domain-we-need-to-buy.com) and at a beta/development basis at [beta.some-domain-we-need-to-buy.com](beta.some-domain-we-need-to-buy.com) simply run

> (Instructions for dependency installations go here; Contact Mark Eyer for details.)
> python3 main.py

To start the frontend(s), of which the primary web-based one can be found in production at [some-domain-we-need-to-buy.com](some-domain-we-need-to-buy.com), follow the instructions in the /src/frontends subdirectories. In general, it contains an early iteration of a front-end built using Kumu. We want to build something similar but better.
 - [kumu instance](https://embed.kumu.io/6cbeee6faebd8cc57590da7b83c4d457#default)
 - [demo video](https://www.youtube.com/watch?v=jZyLSRCba_M)

## File Structure

├── CONTRIBUTING.md **Outlines how to contribute to the project. Still under construction.**
├── LICENSE **Standard Apache2 license.**
├── README.md **Information about this repository.**
├── docs **This is the directory where all the documentation is stored.**
├── main.py **Launchpoint for the app's backend. Run python3 main.py**
├── mkdocs.yml **Documentation configuration settings. (TODO: Determine if can be moved into /docs)**
├── pdm.lock **Project dependency file, generated via PDM.**
├── pyproject.toml **Project dependency settings, used by PDM.**
├── src **Source code directory.**
│   ├── backend **The backend, a standalone hub. Internally organized using [hexagonal architecture](https://en.wikipedia.org/wiki/Hexagonal_architecture_(software)).**
│   │   ├── administration **Used by repository maintainers to hold code for internal administrative tools.**
│   │   ├── biz_logic **The main business logic "guts" of the application. Organized around the ["Harvest, Bottle, Mix"](https://docs.google.com/presentation/d/1jE0-VBikgAd-E6XSRTEkt_RxI190uVlsWg11fB6YgXw/edit?usp=sharing) architecture developed by Schwartz et al.**
│   │   │   ├── bottle
│   │   │   ├── harvest
│   │   │   │   ├── endpoint.py **The app uses RESTful endpoints to connect with frontend spokes, via FastAPI.**
│   │   │   │   └── otherfiles.py **A bit tounge in cheek, otherfiles.py is a placeholder for the various other files related to business logic (such as ETL pipelines).**
│   │   │   ├── mix
│   │   │   └── scripts **Directory for miscellaneous stand-alone scripts which predate our overall architecture, primarily used for harvesting.**
│   │   ├── notification **The module for centralized notifications (e.g., sending emails when background scripts complete.)**
│   │   └── persistence **The module for all things database and data persistence related.**
│   └── frontends
│       └── moss-react-app **A standalone react-based website "spoke" which makes RESTful API calls to the backend "hub"**
└── tests **A directory/module which contains all unit/integration tests for src/**

## Contributing

We are still in the process of writing up all our formal procedures on how to contribute code to this repository. A rough draft is located [here](CONTRIBUTING.md) While we accept outside pull requests, the best way to get your contribution accepted is to contact Jon Starr (jring-o) and he can connect you with our weekly technical meetings and give you a brief orientation.

We follow NumFOCUS's [code of conduct](https://numfocus.org/code-of-conduct).

## Core Maintainers

Here are the people who regularly attend weekly meetings where we discuss the technical details of the project. People are listed alphabetically by last/family name. (TODO: Add contact email and/or github username for each person.)

* Dave Bunten
* Mark Eyer
* Victor Lu
* Guy Pavlov
* Sam Schwartz (samuel.d.schwartz@gmail.com)
* Jon Starr
* Peculiar Umeh
* Max Vasiliev
* Boris Veytsman
* Susie Yu
