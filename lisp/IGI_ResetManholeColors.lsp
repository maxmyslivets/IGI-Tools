(defun c:IGI_ResetManholeColors ( / acDoc pfx_ansi sfx_ansi pfx_utf8 sfx_utf8 blkList blkName layout ent count )
  (vl-load-com)
  (setq acDoc (vla-get-ActiveDocument (vlax-get-acad-object)))

  ;; Генерируем префиксы и суффиксы в кодах ASCII / Юникод
  (setq pfx_ansi (strcat (chr 209) (chr 207) "_")   ;; "СП_" в ANSI
        sfx_ansi (strcat "." (chr 235)))            ;; ".л" в ANSI

  (setq pfx_utf8 (strcat (chr 208) (chr 161) (chr 208) (chr 159) "_") ;; "СП_" в UTF-8
        sfx_utf8 (strcat "." (chr 208) (chr 187)))                   ;; ".л" в UTF-8

  (setq blkList nil)

  ;; Генерируем точные имена для блоков БЕЗ суффикса (Добавлены 4.1.2.9 и 4.8.5.1)
  (foreach num '(
                 "4.1.1.1" "4.1.2.1" "4.1.2.2" "4.1.2.3" "4.1.2.4"
                 "4.1.2.5" "4.1.2.7" "4.1.2.8" "4.1.2.9" "4.2.1"
                 "4.2.2"   "4.3.1.1" "4.8.5.1"
                )
    (setq blkList (cons (strcase (strcat pfx_ansi num) t) blkList))
    (setq blkList (cons (strcase (strcat pfx_utf8 num) t) blkList))
  )

  ;; Генерируем точные имена для блоков С суффиксом ".л" (Добавлен 4.1.2.9)
  (foreach num '("4.1.2.1" "4.1.2.2" "4.1.2.3" "4.1.2.4" "4.1.2.5" "4.1.2.7" "4.1.2.8" "4.1.2.9" "4.2.2")
    (setq blkList (cons (strcase (strcat pfx_ansi num sfx_ansi) t) blkList))
    (setq blkList (cons (strcase (strcat pfx_utf8 num sfx_utf8) t) blkList))
  )

  (vla-StartUndoMark acDoc)
  (setq count 0)

  ;; Перебор всех пространств чертежа
  (vlax-for layout (vla-get-Layouts acDoc)
    (vlax-for ent (vla-get-Block layout)
      (if (= (vla-get-ObjectName ent) "AcDbBlockReference")
        (progn
          (setq blkName (strcase (vla-get-EffectiveName ent) t))
          (if (member blkName blkList)
            (progn
              (vla-put-Color ent 0) ;; 0 = По блоку
              (setq count (1+ count))
            )
          )
        )
      )
    )
  )

  (vla-EndUndoMark acDoc)

  (princ (strcat "\n[IGI Tools] Colors reset to ByBlock. Processed: " (itoa count) " blocks."))
  (princ)
)
