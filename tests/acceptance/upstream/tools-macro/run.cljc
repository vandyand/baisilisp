;; Exercise every public API through deterministic data or evaluated results.
(load-file "tests/acceptance/upstream/tools-macro/port/src/basilisp/tools/macro.cljc")
(alias 'tm 'basilisp.tools.macro)

(defn plus [a b] (+ a b))
(tm/defsymbolmacro sum-2-3 (plus 2 3))

(tm/deftemplate pair-template [x y] [x y])

(println
 (pr-str
  {:macrolet
   (macroexpand-1 '(tm/macrolet [(duplicate [form] `(~form ~form))]
                    (duplicate x)))
   :symbol-macrolet
   (macroexpand-1 '(tm/symbol-macrolet [x xx y yy]
                    (exp [a y] (x y))))
   :lexical-protection
   (macroexpand-1 '(tm/symbol-macrolet [x foo z bar]
                    (let [a x b y x b] [a b x z])))
   :function-protection
   (macroexpand-1 '(tm/symbol-macrolet [x foo z bar]
                    (fn ([x y] [x y z]) ([x y z] [x y z]))))
   :mexpand-all
   (tm/mexpand-all '(let [object (fn [] 3)] (object)))
   :symbol-result
   (tm/with-symbol-macros (+ 1 sum-2-3))
   :template-result
   (pair-template :left :right)
   :attributes
   (let [[n args] (tm/name-with-attributes '^:private thing
                                             '("a doc" {:added "1.0"} [x]))]
     [(meta n) args])
   :qualified-rejected
   (try
     (macroexpand-1 '(tm/macrolet [(some.ns/nope [] :nope)] :unreachable))
     false
     (catch #?(:lpy python/Exception :default Exception) _ true))}))
