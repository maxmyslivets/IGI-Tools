(defun c:IGI_SetManholeColors ( / acDoc pfx_ansi sfx_ansi pfx_utf8 sfx_utf8 blkList blkName layout ent count )
  (vl-load-com)
  (setq acDoc (vla-get-ActiveDocument (vlax-get-acad-object)))

  ;; Генерируем префиксы и суффиксы в кодах ASCII / Юникод
  ;; 1. Вариант для Windows-1251 / ANSI (AutoCAD 2020 и старее)
  (setq pfx_ansi (strcat (chr 209) (chr 207) "_")   ;; "СП_" в ANSI
        sfx_ansi (strcat "." (chr 235)))            ;; ".л" в ANSI

  ;; 2. Вариант для UTF-8 (AutoCAD 2021 - 2027+)
  ;; В UTF-8 русские буквы кодируются парами байтов
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

  ;; Перебор пространств чертежа
  (vlax-for layout (vla-get-Layouts acDoc)
    (vlax-for ent (vla-get-Block layout)
      (if (= (vla-get-ObjectName ent) "AcDbBlockReference")
        (progn
          ;; Читаем ТОЧНОЕ имя блока из памяти AutoCAD
          (setq blkName (strcase (vla-get-EffectiveName ent) t))

          ;; Сравниваем символ-в-символ без масок
          (if (member blkName blkList)
            (progn
              (vla-put-Color ent 256) ;; 256 = По слою
              (setq count (1+ count))
            )
          )
        )
      )
    )
  )

  (vla-EndUndoMark acDoc)

  (princ (strcat "\n[IGI Tools] Colors set to ByLayer. Processed: " (itoa count) " blocks."))
  (princ)
)
