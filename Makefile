# ============================================================================
# IGI-Tools Makefile — GNU Make (Windows: Git Bash / scoop / chocolatey)
# Dev-цикл: CADPyRx bundle + AutoLISP + CUIX
#
# Pass-through to PowerShell scripts:
#   make deploy ARGS="-Version major"
#   make installer ARGS="-SkipBundle -IsccPath C:/Inno/ISCC.exe"
#   make bundle Version=minor
#   make deploy-fast ARGS="-NoBump -Junction"
# ============================================================================

SCRIPT_DIR      := scripts
BUILD_BUNDLE    := $(SCRIPT_DIR)/build-bundle.ps1
DEPLOY_DEV      := $(SCRIPT_DIR)/deploy-dev.ps1
BUILD_INSTALLER := $(SCRIPT_DIR)/build-installer.ps1

DIST_DIR        := dist
DIST_BUNDLE     := $(DIST_DIR)/IGITools.bundle
VERSION_FILE    := VERSION

PS              := powershell -NoProfile -ExecutionPolicy Bypass
PS_FILE         := $(PS) -File
PS_CMD          := $(PS) -Command

# Extra script arguments (any PowerShell params for the target script).
ARGS ?=

# Convenience: Version=major|minor|patch|X.Y.Z  →  -Version ...
Version ?=
ifneq ($(Version),)
VERSION_ARG := -Version $(Version)
else
VERSION_ARG :=
endif

.DEFAULT_GOAL := help

.PHONY: help info all bundle bundle-fast deploy deploy-fast deploy-junction
.PHONY: installer installer-fast clean version

# ============================================================================
# Targets
# ============================================================================

## help — справка по target'ам
help:
	@echo === IGI-Tools (dev) ===
	@echo.
	@echo Targets:
	@echo   make bundle            Сборка dist/IGITools.bundle (+ python-embed)
	@echo   make bundle-fast       Сборка без Contents/runtime (~структура only)
	@echo   make deploy            Сборка + установка в ApplicationPlugins (admin)
	@echo   make deploy-fast       Deploy без повторного копирования runtime
	@echo   make deploy-junction   Deploy через junction на dist
	@echo   make installer         Bundle + Inno Setup EXE
	@echo   make installer-fast    Installer без копирования runtime
	@echo   make version           Показать VERSION
	@echo   make clean             Удалить dist/
	@echo   make info / help
	@echo.
	@echo Args (любые параметры скрипта):
	@echo   make deploy ARGS="-Version major"
	@echo   make bundle Version=minor
	@echo   make installer ARGS="-SkipBundle -IsccPath D:/ISCC.exe"
	@echo   make deploy-fast ARGS="-NoBump"
	@echo.
	@echo Версия (файл VERSION): по умолчанию +0.0.1; Version=minor / major
	@echo Скрипты: $(BUILD_BUNDLE), $(DEPLOY_DEV), $(BUILD_INSTALLER)

## info — пути проекта
info:
	@echo === IGI-Tools project ===
	@echo.
	@echo   VERSION:           $(VERSION_FILE)
	@echo   Bundle template:   bundle/
	@echo   LISP sources:      lisp/
	@echo   Python:            python/
	@echo   CUIX:              ui/igi_tools.cuix
	@echo   Runtime (local):   python-embed/  (gitignore)
	@echo   Dist:              $(DIST_BUNDLE)
	@echo   Build:             $(BUILD_BUNDLE)
	@echo   Deploy:            $(DEPLOY_DEV)
	@echo   Installer:         $(BUILD_INSTALLER)
	@echo   ISS:               installer/IGITools-setup.iss
	@echo   ARGS:              $(ARGS)
	@echo   Version:           $(Version)

## version — текущая версия из VERSION
version:
	@$(PS_CMD) "Write-Host ((Get-Content -LiteralPath '$(VERSION_FILE)' -Raw).Trim())"

## all — псевдоним для полной сборки bundle
all: bundle

## bundle — полная сборка dist/IGITools.bundle (копирует python-embed)
bundle:
	$(PS_FILE) $(BUILD_BUNDLE) $(VERSION_ARG) $(ARGS)

## bundle-fast — сборка без Contents/runtime
bundle-fast:
	$(PS_FILE) $(BUILD_BUNDLE) -SkipRuntime $(VERSION_ARG) $(ARGS)

## deploy — сборка + копирование в Program Files\...\ApplicationPlugins
deploy:
	$(PS_FILE) $(DEPLOY_DEV) $(VERSION_ARG) $(ARGS)

## deploy-fast — deploy без повторного копирования runtime
deploy-fast:
	$(PS_FILE) $(DEPLOY_DEV) -SkipRuntime $(VERSION_ARG) $(ARGS)

## deploy-junction — junction ApplicationPlugins -> dist
deploy-junction:
	$(PS_FILE) $(DEPLOY_DEV) -Junction $(VERSION_ARG) $(ARGS)

## installer — bundle + Inno Setup
installer:
	$(PS_FILE) $(BUILD_INSTALLER) $(VERSION_ARG) $(ARGS)

## installer-fast — installer без копирования runtime при сборке bundle
installer-fast:
	$(PS_FILE) $(BUILD_INSTALLER) -SkipRuntime $(VERSION_ARG) $(ARGS)

## clean — удалить dist/
clean:
	$(PS_CMD) "if (Test-Path '$(DIST_DIR)') { Remove-Item -Recurse -Force '$(DIST_DIR)'; Write-Host 'Removed $(DIST_DIR)/' } else { Write-Host 'Nothing to clean' }"
