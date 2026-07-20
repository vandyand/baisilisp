;; Derived from clojure/tools.macro at revision 9cd558da812045f7621ea4063228fbb78288c6db.
;; Copyright (c) Konrad Hinsen 2011. Eclipse Public License 1.0.
(ns basilisp.tools.macro
  (:require #?(:lpy [basilisp.string :as string]
               :default [clojure.string :as string])))

(def ^{:private true} special-forms
  #?(:lpy (into #{} (filter special-symbol?
                            '[await catch def deftype* do finally fn* if import* . .-
                              let* letfn* loop* quote reify* recur require* set! throw
                              try var yield]))
     :default (into #{} (keys clojure.lang.Compiler/specials))))

(def ^{:dynamic true :private true} macro-fns {})
(def ^{:dynamic true :private true} macro-symbols {})
(def ^{:dynamic true :private true} protected-symbols #{})

(defn- protected? [symbol]
  (or (contains? protected-symbols symbol)
      (let [s (str symbol)]
        (or (= "." (subs s 0 1)) (= "." (subs s (dec (count s))))))))

(defn- expand-symbol [symbol]
  (cond (protected? symbol) symbol
        (contains? macro-symbols symbol) (get macro-symbols symbol)
        :else (let [v #?(:lpy (resolve symbol)
                          :default (try (resolve symbol)
                                        (catch java.lang.ClassNotFoundException _ nil)))
                    m (meta v)]
                (if (:symbol-macro m) (var-get v) symbol))))

(defn- expand-1 [form]
  (cond
    (seq? form)
    (let [f (first form)]
      (cond (contains? special-forms f) form
            (and (not (protected? f)) (contains? macro-fns f))
            (apply (get macro-fns f) (rest form))
            (symbol? f)
            (cond (protected? f) form
                  (class? (ns-resolve *ns* f)) form
                  :else (let [exp (expand-symbol f)]
                          (if (= exp f) (macroexpand-1 form) (cons exp (rest form)))))
            :else (macroexpand-1 form)))
    (symbol? form) (expand-symbol form)
    :else form))

(defn- expand [form]
  (let [ex (expand-1 form)] (if (identical? ex form) form (recur ex))))

(declare expand-all)

(defn- expand-args
  ([form] (expand-args form 1))
  ([form n] (doall (concat (take n form) (map expand-all (drop n form))))))

(defn- expand-bindings [bindings exprs]
  (if (empty? bindings)
    (list (doall (map expand-all exprs)))
    (let [[[s b] & bindings] bindings
          b (expand-all b)]
      (binding [protected-symbols (conj protected-symbols s)]
        (doall (cons [s b] (expand-bindings bindings exprs)))))))

(defn- expand-with-bindings [form]
  (let [f (first form)
        bindings (partition 2 (second form))
        exprs (rest (rest form))
        expanded (expand-bindings bindings exprs)
        bindings (vec (apply concat (butlast expanded)))
        exprs (last expanded)]
    (cons f (cons bindings exprs))))

(defn- expand-fn-body [[args & exprs]]
  (binding [protected-symbols (reduce conj protected-symbols
                                     (filter #(not (= % '&)) args))]
    (cons args (doall (map expand-all exprs)))))

(defn- expand-fn [form]
  (let [[f & bodies] form
        name (when (symbol? (first bodies)) (first bodies))
        bodies (if (symbol? (first bodies)) (rest bodies) bodies)
        bodies (if (vector? (first bodies)) (list bodies) bodies)
        bodies (doall (map expand-fn-body bodies))]
    (if (nil? name) (cons f bodies) (cons f (cons name bodies)))))

(defn- expand-deftype [[symbol typename classname fields implements interfaces & methods]]
  (assert (= implements :implements))
  (concat (list symbol typename classname fields implements interfaces)
          (doall (map #(expand-args % 2) methods))))

(defn- expand-reify [[symbol interfaces & methods]]
  (cons symbol (cons interfaces (map #(expand-args % 2) methods))))

(def ^{:private true} special-form-handlers
  {'quote identity, 'var identity, 'def #(expand-args % 2), 'new #(expand-args % 2),
   'let* expand-with-bindings, 'letfn* expand-with-bindings, 'loop* expand-with-bindings,
   'fn* expand-fn, 'deftype* expand-deftype, 'reify* expand-reify})

(defn- expand-list [form]
  (let [f (first form)]
    (if (symbol? f)
      (if (contains? special-forms f)
        ((get special-form-handlers f expand-args) form)
        (expand-args form))
      (doall (map expand-all form)))))

(defn- expand-all [form]
  (let [exp (expand form)]
    (cond (symbol? exp) exp
          (seq? exp) (expand-list exp)
          (vector? exp) (into [] (map expand-all exp))
          (map? exp) (into {} (map expand-all (seq exp)))
          :else exp)))

(defn- check-not-qualified [symbols]
  (when (not-every? nil? (map namespace symbols))
    (throw #?(:lpy (ex-info (str "Can't macrolet qualified symbol(s): "
                                  (string/join ", " (map str (filter namespace symbols)))) {})
              :default (Exception. (str "Can't macrolet qualified symbol(s): "
                                        (string/join ", " (map str (filter namespace symbols))))))))
  symbols)

(defmacro macrolet [fn-bindings & exprs]
  (let [names (check-not-qualified (map first fn-bindings))
        name-map (into {} (map (fn [n] [(list 'quote n) n]) names))
        macro-map (eval `(letfn ~fn-bindings ~name-map))]
    (binding [macro-fns (merge macro-fns macro-map)
              macro-symbols (apply dissoc macro-symbols names)]
      `(do ~@(doall (map expand-all exprs))))))

(defmacro symbol-macrolet [symbol-bindings & exprs]
  (let [symbol-map (into {} (map vec (partition 2 symbol-bindings)))
        names (check-not-qualified (keys symbol-map))]
    (binding [macro-fns (apply dissoc macro-fns names)
              macro-symbols (merge macro-symbols symbol-map)]
      `(do ~@(doall (map expand-all exprs))))))

(defmacro defsymbolmacro [symbol expansion]
  (let [meta-map (assoc (or (meta symbol) {}) :symbol-macro true)]
    `(def ~(with-meta symbol meta-map) (quote ~expansion))))

(defmacro with-symbol-macros [& exprs]
  `(do ~@(doall (map expand-all exprs))))

(defmacro deftemplate [name params & forms]
  (let [param-map (for [p params] (list (list 'quote p) (gensym)))
        template-params (vec (map second param-map))
        param-map (vec (apply concat param-map))
        expansion (list `list (list 'quote `symbol-macrolet) param-map
                        (list 'quote (cons 'do forms)))]
    `(defmacro ~name ~template-params ~expansion)))

(defn mexpand-1 [form]
  (binding [macro-fns {} macro-symbols {} protected-symbols #{}] (expand-1 form)))

(defn mexpand [form]
  (binding [macro-fns {} macro-symbols {} protected-symbols #{}] (expand form)))

(defn mexpand-all [form]
  (binding [macro-fns {} macro-symbols {} protected-symbols #{}] (expand-all form)))

(defn name-with-attributes [name macro-args]
  (let [[docstring macro-args] (if (string? (first macro-args))
                                 [(first macro-args) (next macro-args)] [nil macro-args])
        [attr macro-args] (if (map? (first macro-args))
                            [(first macro-args) (next macro-args)] [{} macro-args])
        attr (if docstring (assoc attr :doc docstring) attr)
        attr (if (meta name) (conj (meta name) attr) attr)]
    [(with-meta name attr) macro-args]))
