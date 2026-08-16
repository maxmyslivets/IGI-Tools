;; IGIToolsLoader.lsp — автозагрузка AutoLISP / VLX из Contents/Lisp
;; Загружается через PackageContents.xml (LoadOnAutoCADStartup).
;;
;; Важно: PackageContents.xml лежит в корне bundle и НЕ входит в SupportPath,
;; поэтому каталог скриптов определяем через findfile самого загрузчика
;; (SupportPath включает ./Contents/Lisp/).

(vl-load-com)

(defun igi-tools-lisp-dir ( / self)
  (setq self (findfile "IGIToolsLoader.lsp"))
  (if self
    (vl-filename-directory self)
    nil
  )
)

(defun igi-tools-load-file (path / err)
  (cond
    ((not (findfile path))
      (princ (strcat "\n[IGI Tools] Не найден: " path))
      nil
    )
    (T
      (setq err (vl-catch-all-apply 'load (list path)))
      (if (vl-catch-all-error-p err)
        (progn
          (princ (strcat "\n[IGI Tools] Ошибка загрузки: " path))
          (princ (strcat " — " (vl-catch-all-error-message err)))
          nil
        )
        (progn
          (princ (strcat "\n[IGI Tools] Загружен: " (vl-filename-base path)))
          T
        )
      )
    )
  )
)

(defun igi-tools-load-lisp-folder (dir / files f name count)
  (setq count 0)
  (setq files (vl-directory-files dir nil 1))
  (foreach f files
    (setq name (strcase f))
    (cond
      ((= name "IGITOOLSLOADER.LSP") nil)
      ((or
         (wcmatch name "*.LSP")
         (wcmatch name "*.VLX")
         (wcmatch name "*.FAS")
       )
        (if (igi-tools-load-file (strcat dir "\\" f))
          (setq count (1+ count))
        )
      )
    )
  )
  count
)

(defun load-igi-tools ( / lispDir n)
  (setq lispDir (igi-tools-lisp-dir))
  (cond
    ((null lispDir)
      (princ "\n[IGI Tools] IGIToolsLoader.lsp не в SupportPath — LISP не загружены.")
    )
    (T
      (setq n (igi-tools-load-lisp-folder lispDir))
      (princ (strcat "\n[IGI Tools] LISP/VLX загружено: " (itoa n)))
      (princ (strcat "\n[IGI Tools] Каталог: " lispDir))
    )
  )
  (princ)
)

(load-igi-tools)
(princ "\n[IGI Tools] Готово. Python: IGI_CIRCLES_ON_VERTICES. LISP: см. команды скриптов.")
(princ)
