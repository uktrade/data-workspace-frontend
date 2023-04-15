---
title: Data Workspace Technical Documentation
hide:
  - navigation
  - toc
---

<style>
  .md-typeset h1 {
    display: none;
  }
  
  .md-main__inner {
    margin-top: 0px;
  }

  .md-content__button {
    display: none;
  }

  .dw-image-column img {
    width:  100%;
  }

  @media (min-width: 40.0625em) {
    .dw-row {
      display: flex;
      gap: 12px;
    }

    .dw-image-column {
      flex: 0 0 300px;
    }
  }

  .admonition .dw-start {
    line-height:  1;
    padding-top: 8px;
    padding-bottom: 8px;
    display: block;
    text-align: center;
  }

  @media (min-width: 40.0625em) {
    .admonition .dw-start {
      display: inline-block;
      text-align: left;
    }
  }

  .admonition .dw-start__start-icon {
    margin-left: 5px;
    vertical-align: middle;
    flex-shrink: 0;
    align-self: center;
    forced-color-adjust: auto;
    position: relative;
    top: -1px;
  }
</style>

!!! banner "Host your own data analysis platform"
    <div class="dw-row">
      <div class="dw-column-two-thirds">
      **Data Workspace** is an open source data analysis platform with features for users with a range of technical skills. Features include:

      - a data catalogue for users to discover, filter, and download data
      - a permission system that allows users to only access specific datasets
      - a framework for hosting tools that allows users to analyse data without downloading it, such as through JupyterLab, RStudio, or Theia (a VS Code-like IDE)
      - dashboard creation and hosting

      Data Workspace has been built with features specifically for the Department for Business and Trade. However, we are open to contributions to make this more generic. See [Contributing](./contributing.md) for details on how to make changes for your use case.
      </div>

      <div class="dw-image-column">![Data Workspace image](assets/dw-readme-front-page.png){ width=300px}</div>
    </div>

    <a class="md-button md-button--primary dw-start" href="development/running-locally/">Run Data Workspace locally<svg class="dw-start__start-icon" xmlns="http://www.w3.org/2000/svg" width="17.5" height="19" viewBox="0 0 33 40" focusable="false" aria-hidden="true"><path fill="currentColor" d="M0 0h13l20 20-20 20H0l20-20z"></path></a>
