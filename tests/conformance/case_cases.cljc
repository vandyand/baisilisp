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

(emit-case :case-numeric-family-dispatch
           [(case 0 0 :int 0.0 :double 0M :decimal :default)
            (case 0.0 0 :int 0.0 :double 0M :decimal :default)
            (case 0M 0 :int 0.0 :double 0M :decimal :default)
            (case 0/1 0/1 :ratio 0.0 :double 0M :decimal :default)
            (case -0.0 0 :int -0.0 :zero-float :default)
            (case ##NaN ##NaN :nan 0 :zero :default)
            (case 2 2 :int 2.0 :double 2M :decimal :default)
            (case 2.0 2 :int 2.0 :double 2M :decimal :default)
            (case 2M 2 :int 2.0 :double 2M :decimal :default)
            (case 2/1 2/1 :ratio 2.0 :double 2M :decimal :default)
            (case 1/2 0.5 :double 0.5M :decimal 1/2 :ratio :default)])

(emit-case :case-numeric-group-dispatch
           [(case 1 (1 2 3) :ints (1.0 2.0 3.0) :doubles :default)
            (case 1.0 (1 2 3) :ints (1.0 2.0 3.0) :doubles :default)
            (case 2M (1 2 3) :ints (1M 2M 3M) :decimals :default)
            (case 3/2 (1/2 3/2 5/2) :ratios (1.0 2.0 3.0) :doubles :default)
            (case ##NaN (##NaN) :nan-group ##NaN :nan-single :default)])

(defn generated-case-form [seed]
  (case (mod seed 12)
    0 `(case ~seed ~seed :int ~(double seed) :double :default)
    1 `(case ~(double seed) ~seed :int ~(double seed) :double :default)
    2 `(case ~(bigdec seed) ~seed :int ~(bigdec seed) :decimal :default)
    3 `(case ~(/ seed (inc seed))
         ~(double (/ seed (inc seed))) :double
         ~(/ seed (inc seed)) :ratio
         :default)
    4 `(case ~(mod seed 5)
         (0 1) :low
         (2 3) :mid
         4 :high
         :default)
    5 `(case ~(double (mod seed 5))
         (0 1) :int-group
         (0.0 1.0) :double-low
         (2.0 3.0) :double-mid
         4.0 :double-high
         :default)
    6 `(case ~(bigdec (mod seed 5))
         (0 1) :int-group
         (0M 1M) :decimal-low
         (2M 3M) :decimal-mid
         4M :decimal-high
         :default)
    7 `(case ~(/ (inc (mod seed 5)) 2)
         (1/2 2/2) :ratio-low
         (3/2 4/2) :ratio-mid
         5/2 :ratio-high
         :default)
    8 `(case ~(- seed) ~seed :positive ~(- seed) :negative :default)
    9 `(case ~(str "s" seed) ~(symbol (str "s" seed)) :symbol ~(str "s" seed) :string :default)
    10 `(case ~(keyword (str "k" seed)) ~(keyword (str "k" seed)) :keyword ~(str "k" seed) :string :default)
    `(case ~[(mod seed 3) (mod seed 5)] ~[(mod seed 3) (mod seed 5)] :vector :default)))

(emit-case :seeded-case-numeric-dispatch
           (mapv (fn [seed] (eval (generated-case-form seed)))
                 (range 1 97)))

(emit-case :case-numeric-duplicate-boundaries
           (mapv rejected?
                 ['(case 1 1 :int 1N :bigint :default)
                  '(case 1 1 :int 1/1 :ratio :default)
                  '(case 1 (0 1N 2) :group 3 :other :default)
                  '(case 1 (0 1/1 2) :group 3 :other :default)
                  '(case 1.0 1.0 :double 2 :other :default)
                  '(case -0.0 -0.0 :negative-zero 0.0 :positive-zero :default)
                  '(case 1M 1M :decimal 2 :other :default)
                  '(case ##NaN ##NaN :nan ##NaN :other :default)]))
