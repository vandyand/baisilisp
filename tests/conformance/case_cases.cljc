;; Portable ``case`` dispatch behavior and duplicate-test validation.

(defn emit-case [case value]
  (println (pr-str {:case case :value value})))

(defn rejected? [form]
  (try
    (eval form)
    false
    (catch Exception _ true)))

(defn positive-dispatch [x]
  (case x
    sym :sym-result
    :kw :kw-result
    "string" :string-result
    1 :integer-result
    1.0 :double-result
    1.0M :decimal-result
    1/2 :ratio-result
    \a :character-result
    true :boolean-true-result
    false :boolean-false-result
    nil :nil-result
    [:vec :of :kws] :vec-result
    {:a :map} :map-result
    #{:a :set} :set-result
    (:either :this :or :that) :one-of-multiple-result
    :default-result))

(emit-case :case-positive-dispatch
           [(positive-dispatch 'sym)
            (positive-dispatch :kw)
            (positive-dispatch "string")
            (positive-dispatch 1)
            (positive-dispatch 1.0)
            (positive-dispatch 1.0M)
            (positive-dispatch 1/2)
            (positive-dispatch \a)
            (positive-dispatch true)
            (positive-dispatch false)
            (positive-dispatch nil)
            (positive-dispatch [:vec :of :kws])
            (positive-dispatch {:a :map})
            (positive-dispatch #{:a :set})
            (positive-dispatch :this)
            (positive-dispatch :missing)])

(emit-case :case-no-default
           [(rejected? '(case :missing :present :value))
            (case :present :present :value)])

(emit-case :case-duplicate-test-rejection
           [(rejected? '(case 1 1 :int 1N :bigint :default))
            (rejected? '(case 1 1 :int 1/1 :ratio :default))
            (rejected? '(case :a (:a :b) :group :a :single :default))
            (rejected? '(case \a \a :char-a (a b) :symbol-group :default))
            ;; Distinct numeric families and NaN constants are not duplicate
            ;; constants in JVM Clojure's case dispatch.
            (not (rejected? '(case 1 1 :int 1.0 :double :default)))
            (not (rejected? '(case 1 1 :int 1.0M :decimal :default)))
            (not (rejected? '(case ##NaN ##NaN :first ##NaN :second :default)))])
