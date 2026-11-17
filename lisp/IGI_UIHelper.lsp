;; IGI_UIHelper.lsp — утилиты управления UI: загрузка CUIX, переключение панелей
;; Команды: IGI_LOADCUI, IGI_PALETTES_TOGGLE

(defun _igi-cuix-path ( / loaderDir )
  (setq loaderDir (findfile "IGIToolsLoader.lsp"))
  (if loaderDir
    (strcat (vl-filename-directory loaderDir) "\\..\\Resources\\igi_tools.cuix")
    nil
  )
)

;; ---------------------------------------------------------------------------
;; IGI_LOADCUI — принудительная загрузка CUIX (если панели не появились)
;; ---------------------------------------------------------------------------
(defun c:IGI_LOADCUI ( / cuiPath )
  (vl-load-com)
  (setq cuiPath (_igi-cuix-path))
  (cond
    ((null cuiPath)
      (princ "\n[IGI Tools] IGIToolsLoader.lsp не найден в SupportPath.")
    )
    ((not (findfile cuiPath))
      (princ (strcat "\n[IGI Tools] CUIX не найден: " cuiPath))
    )
    (T
      (command "_.CUILOAD" cuiPath)
      (princ (strcat "\n[IGI Tools] CUIX загружен: " cuiPath))
    )
  )
  (princ)
)

(defun c:IGI_PANEL_TOGGLE ( / acad app mgs mg tbs tb igi-tbs anyVisible show )
  (vl-load-com)
  (setq acad (vlax-get-acad-object))
  (setq app (vla-get-Application acad))
  (setq mgs (vla-get-MenuGroups app))   ;; коллекция MenuGroup

  ;; Собрать все тулбары IGI Tools (любой dock status)
  (setq igi-tbs nil)
  (vlax-for mg mgs
    (setq tbs (vla-get-ToolBars mg))
    (vlax-for tb tbs
      (if (wcmatch (strcase (vla-get-Name tb)) "IGI TOOLS*")
        (setq igi-tbs (cons tb igi-tbs))
      )
    )
  )

  (if (not igi-tbs)
    (princ "\n[IGI Tools] Панели IGI Tools не найдены.")
    (progn
      ;; Есть ли среди панелей IGI Tools хоть одна видимая?
      (setq anyVisible nil)
      (foreach tb igi-tbs
        (if (= (vla-get-Visible tb) :vlax-true)
          (setq anyVisible T)
        )
      )

      (setq show (not anyVisible))  ;; T = показать, nil = скрыть

      (foreach tb igi-tbs
        (vl-catch-all-apply 'vla-put-Visible
          (list tb (if show :vlax-true :vlax-false))
        )
      )

      (princ (strcat "\n[IGI Tools] Панели IGI Tools "
                     (if show "показаны." "скрыты.")
      ))
    )
  )
  (princ)
)
