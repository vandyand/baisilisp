;; Portable edge semantics. Each result is deliberately data-only so Clojure
;; and Basilisp can compare behavior without host class or print differences.

(defn emit-case [case value]
  (println (pr-str {:case case :value value})))

(let [realizations (atom 0)
      values (lazy-seq
              (swap! realizations inc)
              (cons :first
                    (lazy-seq
                     (swap! realizations inc)
                     (cons :second nil))))
      before @realizations
      first-value (first values)
      after-first @realizations
      second-value (first (rest values))
      after-second @realizations]
  (emit-case :lazy-realization
             {:before before
              :first first-value
              :after-first after-first
              :second second-value
              :after-second after-second}))

(let [result (transduce (comp (map inc) (take 3)) conj [] (range 10))]
  (emit-case :transducer-completion result))

(defmacro duplicate-value [value]
  `(let [value# ~value]
     [value# value#]))

(let [expanded (macroexpand '(duplicate-value (+ 1 2)))]
  (emit-case :macroexpand
             {:let-form? (= 'let (first expanded))
              :binding-count (count (second expanded))
              :body-count (count (rest (rest expanded)))}))

(let [value (read-string "^{:tag :portable} [1]")]
  ;; Basilisp retains reader source locations as additional metadata for
  ;; diagnostics; ``:tag`` is the portable user-visible metadata contract.
  (emit-case :reader-metadata {:value value :tag (:tag (meta value))}))

(let [summary #?(:clj (try
                        (throw (ex-info "edge failure" {:edge true}))
                        (catch clojure.lang.ExceptionInfo e
                          {:message (ex-message e) :data (ex-data e) :cause (ex-cause e)}))
                    :lpy (try
                           (throw (ex-info "edge failure" {:edge true}))
                           (catch basilisp.lang.exception/ExceptionInfo e
                             {:message (ex-message e) :data (ex-data e) :cause (ex-cause e)})))]
  (emit-case :ex-info summary))
