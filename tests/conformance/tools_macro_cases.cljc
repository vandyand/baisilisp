;; Portable clojure.tools.macro/basilisp.tools.macro behavior.

#?(:clj
   (require '[clojure.tools.macro :as tm])
   :lpy
   (require '[basilisp.tools.macro :as tm]))

(defn emit-case [case value]
  (println (pr-str {:case case :value value})))

(defn rejected? [f]
  (try
    (f)
    false
    (catch #?(:clj Throwable :lpy python/Exception) _
      true)))

(defn plus [a b] (+ a b))
(defn fixture-inc [x] (+ x 1))

(tm/defsymbolmacro fixture-sum (plus 2 3))
(tm/defsymbolmacro fixture-map {:value fixture-sum})
(tm/deftemplate fixture-pair [x y] {:left x :right y})

(defn attr-summary [name macro-args]
  (let [[n args] (tm/name-with-attributes name macro-args)]
    {:name n
     :meta (meta n)
     :args args}))

(def generated-symbol-forms
  '[(tm/symbol-macrolet [x 1 y 2] (+ x y))
    (tm/symbol-macrolet [x :outer] (let [x :inner y x] [x y]))
    (tm/symbol-macrolet [item :expanded] {:item item :quoted 'item})
    (tm/symbol-macrolet [f fixture-inc x 4] (f x))])

(emit-case :public-surface
           (sort (map name (keys (ns-publics #?(:clj 'clojure.tools.macro
                                                :lpy 'basilisp.tools.macro))))))

(emit-case :macrolet-expansion
           {:basic (macroexpand-1
                    '(tm/macrolet [(duplicate [form] (list form form))]
                       (duplicate x)))
            :lexical-shadow (macroexpand-1
                             '(tm/macrolet [(f [form] (list 'fixture-inc form))]
                                (let [f identity]
                                  (f 1))))
            :local-shadows-symbol (macroexpand-1
                                   '(tm/symbol-macrolet [f dec]
                                      (tm/macrolet [(f [form] (list 'fixture-inc form))]
                                        (f 1))))})

(emit-case :symbol-macro-expansion
           {:form (macroexpand-1
                   '(tm/symbol-macrolet [x xx y yy]
                      (exp [a y] (x y))))
            :lexical (macroexpand-1
                      '(tm/symbol-macrolet [x foo z bar]
                         (let [a x b y x b]
                           [a b x z])))
            :fn-args (macroexpand-1
                      '(tm/symbol-macrolet [x foo z bar]
                         (fn ([x y] [x y z])
                           ([x y z] [x y z]))))})

(emit-case :global-symbol-macros-and-templates
           {:symbol-result (tm/with-symbol-macros (+ 1 fixture-sum))
            :nested-symbol-result (tm/with-symbol-macros fixture-map)
            :template-result (fixture-pair :left :right)
            :mexpand-1 (tm/mexpand-1 'fixture-sum)
            :mexpand (tm/mexpand 'fixture-sum)})

(emit-case :mexpand-all-structures
           {:let-fn (tm/mexpand-all '(let [object (fn [] 3)]
                                       (object)))
            :quoted (tm/mexpand-all '(tm/symbol-macrolet [x replaced]
                                       (quote x)))
            :map-vector (tm/mexpand-all '(tm/symbol-macrolet [x :x y :y]
                                           {:x x :nested [y 'x]}))})

(emit-case :name-with-attributes
           {:plain (attr-summary 'thing '([x]))
            :doc (attr-summary 'thing '("doc" [x]))
            :attr (attr-summary 'thing '({:added "1.0"} [x]))
            :meta-doc-attr (attr-summary '^:private thing
                                          '("doc" {:added "1.0"} [x]))})

(emit-case :rejection-boundaries
           {:qualified-macrolet (rejected?
                                 #(macroexpand-1
                                   '(tm/macrolet [(some.ns/nope [] :nope)]
                                      :unreachable)))
            :qualified-symbol-macrolet (rejected?
                                        #(macroexpand-1
                                          '(tm/symbol-macrolet [some.ns/nope :nope]
                                             :unreachable)))})

(emit-case :generated-symbol-macro-corpus
           (mapv (fn [form]
                   {:form form
                    :expansion (macroexpand-1 form)
                    :full (tm/mexpand-all form)})
                 generated-symbol-forms))
