(defun c:SP92ToPoints ( / ss i ent name effName insPt zAttr zVal pt count)
  (vl-load-com)
  ;; Выбираем все вхождения блоков (включая анонимные *U... для динамических блоков)
  (if (setq ss (ssget '((0 . "INSERT") (2 . "СП_9.2,`*U*"))))
    (progn
      (vla-startundomark (vla-get-activedocument (vlax-get-acad-object)))
      (setq i 0
            count 0)
      (while (< i (sslength ss))
        (setq ent (ssname ss i)
              name (vlax-ename->vla-object ent)
              ;; Получаем "настоящее" имя блока, даже если он динамический
              effName (if (vlax-property-available-p name 'EffectiveName)
                        (vla-get-effectivename name)
                        (vla-get-name name)
                      )
        )

        ;; Проверяем, совпадает ли реальное имя блока с искомым
        (if (= (strcase effName) (strcase "СП_9.2"))
          (progn
            (setq insPt (vlax-get name 'InsertionPoint)
                  zAttr nil)

            ;; Поиск атрибута с именем Z
            (if (= (vla-get-hasattributes name) :vlax-true)
              (foreach attr (vlax-safearray->list (vlax-variant-value (vla-getattributes name)))
                (if (= (strcase (vla-get-tagstring attr)) "Z")
                  (setq zAttr (vla-get-textstring attr))
                )
              )
            )

            ;; Если атрибут найден, преобразуем в число и создаем точку
            (if zAttr
              (progn
                (setq zVal (distof zAttr))
                (if zVal
                  (progn
                    (setq pt (list (car insPt) (cadr insPt) zVal))
                    (entmake (list '(0 . "POINT") (cons 10 pt)))
                    (setq count (1+ count))
                  )
                )
              )
            )
          )
        )
        (setq i (1+ i))
      )
      (vla-endundomark (vla-get-activedocument (vlax-get-acad-object)))
      (princ (strcat "\nГотово! Успешно создано точек: " (itoa count)))
    )
    (princ "\nНа чертеже вообще не выбрано подходящих блоков.")
  )
  (princ)
)
