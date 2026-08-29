(defun c:z2sp92 ( / ss i ent dxf insPt elev blkObj attribs attr layerName delAns lstToDel dynProps prop propName obj oldDimzin oldCmdecho ssDel Cobjs )
  (vl-load-com)
  
  ;; 1. Проверяем наличие целевого блока СП_9.2 в чертеже
  (if (not (tblsearch "BLOCK" "СП_9.2"))
    (progn
      (alert "Ошибка: Блок с именем 'СП_9.2' не найден в чертеже!\nПожалуйста, создайте его перед запуском команды.")
      (exit)
    )
  )

  ;; 2. Выбираем любые объекты (предварительно выделенные или по запросу)
  (setq ss (ssget "_I"))
  (if (not ss)
    (progn
      (princ "\nВыберите любые блоки или точки с координатой Z...")
      (setq ss (ssget))
    )
  )
  
  (if ss
    (progn
      ;; Сохраняем системные переменные и отключаем вывод команд ради скорости
      (setq oldDimzin (getvar "DIMZIN"))
      (setq oldCmdecho (getvar "CMDECHO"))
      (setvar "DIMZIN" 0)
      (setvar "CMDECHO" 0)
      
      (setq Cobjs (vla-get-ActiveDocument (vlax-get-acad-object)))
      (vla-StartUndoMark Cobjs)
      
      (setq i 0)
      (setq lstToDel nil)
      
      ;; Основной цикл обработки объектов
      (repeat (sslength ss)
        (setq ent (ssname ss i))
        (setq dxf (entget ent))
        (setq obj (vlax-ename->vla-object ent))
        
        (setq insPt nil elev nil)
        
        ;; УНИВЕРСАЛЬНЫЙ СБОР КООРДИНАТ:
        (if (assoc 10 dxf)
          (setq insPt (cdr (assoc 10 dxf)))
        )
        
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
            (if (vlax-property-available-p obj 'Elevation)
              (setq elev (vlax-get-property obj 'Elevation))
            )
            (if (not elev)
              (setq elev (caddr insPt))
            )
            
            (if (not elev) (setq elev 0.0))
            (setq layerName (cdr (assoc 8 dxf)))
            (setq insPt (list (car insPt) (cadr insPt) elev))
            
            ;; Вставляем блок "СП_9.2"
            (setq blkObj (vla-InsertBlock 
                           (vla-get-ModelSpace Cobjs)
                           (vlax-3d-point insPt) 
                           "СП_9.2" 
                           0.5 0.5 0.5 0.0))
            
            (vla-put-Layer blkObj layerName)
            (vla-put-Color blkObj 0)
            
            ;; Заполняем динамические свойства
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
            
            ;; Заполняем текстовый атрибут Z
            (setq attribs (vlax-invoke blkObj 'GetAttributes))
            (foreach attr attribs
              (if (= (strcase (vla-get-TagString attr)) "Z")
                (vla-put-TextString attr (rtos elev 2 2))
              )
            )
            
            ;; Собираем исходные имена объектов в список
            (setq lstToDel (cons ent lstToDel))
          )
        )
        (setq i (1+ i))
      )
      
      ;; Выводим сообщение о завершении генерации блоков
      (princ (strcat "\nУспешно обработано объектов и создано блоков: " (itoa (length lstToDel))))
      
      ;; 3. Интерактивный запрос на удаление исходных объектов
      (if lstToDel
        (progn
          (initget "Да Нет Yes No")
          (setq delAns (getkword "\nУдалить исходные объекты (точки/блоки)? [Да/Нет] <Нет>: "))
          (if (or (= delAns "Да") (= delAns "Yes"))
            (progn
              ;; ПАКЕТНОЕ УДАЛЕНИЕ: Создаем один общий набор выбора
              (setq ssDel (ssadd))
              (foreach ent lstToDel
                (ssadd ent ssDel)
              )
              ;; Стираем всё одной командой БЕЗ перерисовки каждого объекта
              (command "_.erase" ssDel "")
              (setq ssDel nil) 
              (princ (strcat "\nУдалено исходных объектов: " (itoa (length lstToDel))))
            )
            (princ "\nИсходные объекты сохранены на чертеже.")
          )
        )
      )
      
      ;; ОДНОКРАТНОЕ ОБНОВЛЕНИЕ ЭКРАНА В КОНЦЕ: Регенерируем чертеж один раз
      (vla-Regen Cobjs acActiveViewport)
      
      ;; Восстанавливаем настройки среды
      (setvar "DIMZIN" oldDimzin)
      (setvar "CMDECHO" oldCmdecho)
      (vla-EndUndoMark Cobjs)
    )
    (princ "\nОбъекты для обработки не выбраны.")
  )
  (princ)
)
(princ "\nСкрипт очищен от нестандартных функций и готов. Команда: z2sp92")
(princ)
