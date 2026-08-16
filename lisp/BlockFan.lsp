(vl-load-com)

(defun c:BlockFan ( / ss i ent blockObj copyCount copiesToCreate basePoint j newObj newAngle )
  (vla-startundomark (vla-get-activedocument (vlax-get-acad-object)))
  
  (princ "\n--- Скрипт создания веера блоков запущен ---")
  
  ;; 1. Получаем набор объектов (сначала ищем предварительный выбор)
  (setq ss (ssget "_I" '((0 . "INSERT"))))
  
  ;; Если предварительного выбора нет, просим пользователя выбрать блоки
  (if (not ss)
    (progn
      (princ "\nВыберите один или несколько блоков: ")
      (setq ss (ssget '((0 . "INSERT"))))
    )
  )
  
  ;; 2. Если блоки выбраны, запрашиваем общее количество
  (if ss
    (progn
      (setq copyCount (getint "\nВведите ОБЩЕЕ количество блоков в веере (включая исходный): "))
      
      (if (and copyCount (> copyCount 0))
        (progn
          ;; Считаем, сколько именно копий нужно создать для каждого блока
          (setq copiesToCreate (- copyCount 1))
          
          ;; Если нужно создать хотя бы одну копию
          (if (> copiesToCreate 0)
            (progn
              ;; Цикл по всем выбранным блокам
              (setq i 0)
              (while (< i (sslength ss))
                (setq ent (ssname ss i))
                (setq blockObj (vlax-ename->vla-object ent))
                
                ;; Получаем базовую точку текущего блока
                (setq basePoint (vla-get-InsertionPoint blockObj))
                
                ;; Цикл создания копий для текущего блока
                (setq j 1)
                (while (<= j copiesToCreate)
                  ;; Делаем копию
                  (setq newObj (vla-copy blockObj))
                  
                  ;; Считаем угол в радианах (+10 градусов за каждый шаг)
                  (setq newAngle (+ (vla-get-Rotation blockObj) (* j (* 15.0 (/ pi 180.0)))))
                  
                  ;; Поворачиваем копию
                  (vla-put-Rotation newObj newAngle)
                  
                  (setq j (1+ j))
                )
                (setq i (1+ i))
              )
              (princ (strcat "\nОбработано блоков: " (itoa (sslength ss)) ". Итоговый веер состоит из " (itoa copyCount) " элементов."))
            )
            (princ "\nВведено 1. Копии не требуются, так как исходный блок уже существует.")
          )
        )
        (princ "\nОшибка: Нужно ввести целое число больше нуля.")
      )
    )
    (princ "\nБлоки не были выбраны.")
  )
  
  (vla-endundomark (vla-get-activedocument (vlax-get-acad-object)))
  (princ)
)

(princ "\nКоманда загружена. Выделите блоки и введите BlockFan, либо введите BlockFan для выбора на месте.")
(princ)
