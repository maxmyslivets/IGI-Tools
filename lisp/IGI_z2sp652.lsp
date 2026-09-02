;; Глобальная переменная для хранения допуска в рамках сессии AutoCAD
(if (not *z2sp652-dist*)
  (setq *z2sp652-dist* 0.2) ; Значение по умолчанию при первом запуске
)

(defun c:IGI_z2sp652 ( / ss i ent dxf insPt elev obj layerName items pt1 pt2 item1 item2 tmpDist remItems
                     paired used hObj zObj insertPt blkObj dynProps prop propName attribs attr
                     oldDimzin oldCmdecho ssDel Cobjs totalCreated lstToDel delAns )
  (vl-load-com)

  ;; 1. Проверяем наличие целевого блока СП_6.5.2 в чертеже
  (if (not (tblsearch "BLOCK" "СП_6.5.2"))
    (progn
      (alert "Ошибка: Блок с именем 'СП_6.5.2' не найден в чертеже!\nПожалуйста, добавьте его в чертеж перед запуском команды.")
      (exit)
    )
  )

  ;; 2. Выбор объектов и настройка допуска
  (setq ss (ssget "_I")) ; Проверяем предварительный выбор
  (if (not ss)
    (progn
      ;; Если предварительного выбора нет, даем возможность настроить допуск
      (initget 2) ; Запрет ввода нуля
      (setq tmpDist (getdist (strcat "\nЗадайте допуск расстояния между объектами <" (rtos *z2sp652-dist* 2 3) ">: ")))
      (if tmpDist (setq *z2sp652-dist* tmpDist)) ; Перезаписываем, если введено новое значение

      (princ "\nВыберите объекты (точки/блоки) для поиска пар...")
      (setq ss (ssget))
    )
  )

  (if ss
    (progn
      ;; Отключаем подавление нулей и эхо команд ради стабильности работы rtos и скорости
      (setq oldDimzin (getvar "DIMZIN"))
      (setq oldCmdecho (getvar "CMDECHO"))
      (setvar "DIMZIN" 0)
      (setvar "CMDECHO" 0)

      (setq Cobjs (vla-get-ActiveDocument (vlax-get-acad-object)))
      (vla-StartUndoMark Cobjs)

      (setq i 0
            items nil
            lstToDel nil
            totalCreated 0
      )

      ;; Шаг 1: Извлекаем координаты и данные всех выбранных объектов
      (repeat (sslength ss)
        (setq ent (ssname ss i))
        (setq dxf (entget ent))
        (setq obj (vlax-ename->vla-object ent))
        (setq insPt nil elev nil)

        ;; Поиск координат X,Y
        (if (assoc 10 dxf) (setq insPt (cdr (assoc 10 dxf))))
        (if (not insPt)
          (cond
            ((vlax-property-available-p obj 'AnchorPoint)
             (setq insPt (vlax-safearray->list (vlax-variant-value (vlax-get-property obj 'AnchorPoint)))))
            ((vlax-property-available-p obj 'Location)
             (setq insPt (vlax-safearray->list (vlax-variant-value (vlax-get-property obj 'Location)))))
          )
        )

        (if insPt
          (progn
            ;; Поиск отметки Z
            (if (vlax-property-available-p obj 'Elevation)
              (setq elev (vlax-get-property obj 'Elevation))
            )
            (if (not elev) (setq elev (caddr insPt)))
            (if (not elev) (setq elev 0.0))

            (setq layerName (cdr (assoc 8 dxf)))
            ;; Сохраняем структуру: (имя_примитива , (X Y Z) , слой)
            (setq items (cons (list ent (list (car insPt) (cadr insPt) elev) layerName) items))
          )
        )
        (setq i (1+ i))
      )

      ;; Шаг 2: Алгоритм поиска пар по допуску в плане (X, Y)
      (setq used nil) ; Список уже обработанных объектов (чтобы не дублировать)

      (while items
        (setq item1 (car items)
              items (cdr items))

        (if (not (member (car item1) used))
          (progn
            (setq pt1 (cadr item1)
                  paired nil)

            ;; Ищем пару среди оставшихся объектов
            (setq remItems items)
            (while (and remItems (not paired))
              (setq item2 (car remItems)
                    remItems (cdr remItems))

              (if (not (member (car item2) used))
                (progn
                  (setq pt2 (cadr item2))
                  ;; Считаем 2D расстояние (только X и Y)
                  (if (<= (distance (list (car pt1) (cadr pt1)) (list (car pt2) (cadr pt2))) *z2sp652-dist*)
                    (setq paired item2)
                  )
                )
              )
            )

            ;; Шаг 3: Если пара найдена, обрабатываем её
            (if paired
              (progn
                ;; Помечаем оба объекта как использованные
                (setq used (cons (car item1) (cons (car paired) used)))

                ;; Определяем кто выше (H), а кто ниже (Z)
                (if (>= (caddr (cadr item1)) (caddr (cadr paired)))
                  (setq hObj item1 zObj paired)
                  (setq hObj paired zObj item1)
                )

                ;; МЕНЯЕМ ЛОГИКУ: Точка вставки берется строго из плановых координат верхнего объекта (hObj),
                ;; а высотная отметка (Z) — из нижнего объекта (zObj)
                (setq insertPt (list
                                 (car (cadr hObj))
                                 (cadr (cadr hObj))
                                 (caddr (cadr zObj))
                               ))

                ;; Вставляем блок "СП_6.5.2" на слой верхнего объекта (hObj)
                (setq blkObj (vla-InsertBlock
                               (vla-get-ModelSpace Cobjs)
                               (vlax-3d-point insertPt)
                               "СП_6.5.2"
                               0.5 0.5 0.5 0.0))

                (vla-put-Layer blkObj (caddr hObj))
                (vla-put-Color blkObj 0)

                ;; Заполняем динамические свойства (если они есть в блоке)
                (if (= (vla-get-IsDynamicBlock blkObj) :vlax-true)
                  (progn
                    (setq dynProps (vlax-safearray->list (vlax-variant-value (vla-GetDynamicBlockProperties blkObj))))
                    (foreach prop dynProps
                      (setq propName (vla-get-PropertyName prop))
                      (cond
                        ((= (strcase propName) (strcase "Положение X"))
                         (vlax-put-property prop 'Value 0.0)
                        )
                        ((= (strcase propName) (strcase "Положение Y"))
                         (vlax-put-property prop 'Value -0.65)
                        )
                      )
                    )
                  )
                )

                ;; Заполняем текстовые атрибуты H и Z
                (setq attribs (vlax-invoke blkObj 'GetAttributes))
                (foreach attr attribs
                  (cond
                    ((= (strcase (vla-get-TagString attr)) "H")
                     (vla-put-TextString attr (rtos (caddr (cadr hObj)) 2 2))
                    )
                    ((= (strcase (vla-get-TagString attr)) "Z")
                     (vla-put-TextString attr (rtos (caddr (cadr zObj)) 2 2))
                    )
                  )
                )

                ;; Запоминаем элементы для последующего удаления
                (setq lstToDel (cons (car hObj) (cons (car zObj) lstToDel)))
                (setq totalCreated (1+ totalCreated))
              )
            )
          )
        )
      )

      ;; 3. Финализация и интерфейс
      (princ (strcat "\nУспешно сформировано пар и создано блоков 'СП_6.5.2': " (itoa totalCreated)))
      (princ (strcat "\nИспользовано объектов: " (itoa (length lstToDel))))

      ;; Запрос на удаление исходных парных объектов
      (if lstToDel
        (progn
          (initget "Да Нет Yes No")
          (setq delAns (getkword "\nУдалить исходные объекты, вошедшие в пары? [Да/Нет] <Нет>: "))
          (if (or (= delAns "Да") (= delAns "Yes"))
            (progn
              (setq ssDel (ssadd))
              (foreach ent lstToDel (ssadd ent ssDel))
              (command "_.erase" ssDel "")
              (setq ssDel nil)
              (princ (strcat "\nУдалено исходных объектов: " (itoa (length lstToDel))))
            )
            (princ "\nИсходные объекты сохранены на чертеже.")
          )
        )
      )

      (vla-Regen Cobjs acActiveViewport)
      (setvar "DIMZIN" oldDimzin)
      (setvar "CMDECHO" oldCmdecho)
      (vla-EndUndoMark Cobjs)
    )
    (princ "\nОбъекты для обработки не выбраны.")
  )
  (princ)
)
(princ "\nСкрипт парной расстановки блоков готов. Команда: z2sp652")
(princ)
