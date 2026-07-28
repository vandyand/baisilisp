;; Portable clojure.core Var, thread-binding, and root-redefinition helper
;; semantics. The low-level push/pop cases are wrapped in try/finally so failed
;; assertions do not leak thread-local binding frames.

(defn emit-case [case value]
  (println (pr-str {:case case :value value})))

(defn rejected? [f]
  (try
    (f)
    false
    (catch #?(:clj Throwable :lpy python/Exception) _
      true)))

(def ^:dynamic *var-binding-probe* :root)
(def ^:dynamic *var-binding-other* 10)
(def non-dynamic-probe :plain-root)

(def ^:redef redef-value :root-value)
(def ^:redef redef-fn (fn [x] [:root-fn x]))

(defn binding-summary [bindings]
  (into (sorted-map)
        (map (fn [[v value]]
               [(:name (meta v)) value])
             bindings)))

(emit-case :thread-local-var-binding-helpers
           {:root [(var-get #'*var-binding-probe*)
                   (thread-bound? #'*var-binding-probe*)
                   (thread-bound?)
                   (rejected? #(var-set #'*var-binding-probe* :outside))]
            :binding [(binding [*var-binding-probe* :bound]
                        [(var-get #'*var-binding-probe*)
                         *var-binding-probe*
                         (thread-bound? #'*var-binding-probe*)
                         (var-set #'*var-binding-probe* :mutated)
                         (var-get #'*var-binding-probe*)])
                      (var-get #'*var-binding-probe*)]
            :with-bindings* [(with-bindings* {#'*var-binding-probe* :wb
                                              #'*var-binding-other* 42}
                               (fn [suffix]
                                 [(var-get #'*var-binding-probe*)
                                  (var-get #'*var-binding-other*)
                                  (thread-bound? #'*var-binding-probe*
                                                 #'*var-binding-other*)
                                  (str (name (var-get #'*var-binding-probe*))
                                       suffix)])
                               "-done")
                             (var-get #'*var-binding-probe*)
                             (var-get #'*var-binding-other*)]
            :push-pop [(let [push-ret (push-thread-bindings
                                       {#'*var-binding-probe* :pushed})
                             bindings (get-thread-bindings)
                             inside [(var-get #'*var-binding-probe*)
                                     (thread-bound? #'*var-binding-probe*)
                                     (get bindings #'*var-binding-probe*)
                                     (contains? bindings #'*var-binding-other*)]]
                         (try
                           [push-ret inside]
                           (finally
                             (pop-thread-bindings))))
                       (var-get #'*var-binding-probe*)
                       (rejected? #(push-thread-bindings {#'non-dynamic-probe
                                                          :bad}))]})

(emit-case :with-redefs-root-restoration
           {:macro [(with-redefs [redef-value :macro-value
                                  redef-fn (fn [x] [:macro-fn x])]
                      [(var-get #'redef-value)
                       redef-value
                       (redef-fn :x)])
                    [(var-get #'redef-value)
                     (redef-fn :x)]]
            :function [(with-redefs-fn {#'redef-value :fn-value
                                        #'redef-fn (fn [x] [:fn-redef x])}
                         (fn []
                           [(var-get #'redef-value)
                            (redef-fn :y)]))
                       [(var-get #'redef-value)
                        (redef-fn :y)]]
            :exception [(rejected? #(with-redefs [redef-value :exception-value]
                                      (throw
                                       #?(:clj (RuntimeException. "expected")
                                          :lpy (python/RuntimeError "expected")))))
                        (var-get #'redef-value)]
            :degenerate-shape [(rejected? #(eval '(with-redefs [] :bad)))
                               (rejected? #(eval '(with-redefs [redef-value] :bad)))]})

(emit-case :seeded-var-binding-fuzz
           (mapv (fn [n]
                   (let [initial (* n 10)]
                     (binding [*var-binding-other* initial]
                       (let [before (var-get #'*var-binding-other*)
                             set-ret (var-set #'*var-binding-other* (+ before n))
                             after (var-get #'*var-binding-other*)]
                         {:n n
                          :before before
                          :set-ret set-ret
                          :after after
                          :thread-bound? (thread-bound? #'*var-binding-other*)}))))
                 (range -8 9)))
