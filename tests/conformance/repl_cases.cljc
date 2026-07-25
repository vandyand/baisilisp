;; Portable clojure.repl/basilisp.repl semantic coverage.
;;
;; Exact rendered documentation, source, and stack traces are host-shaped. This
;; fixture compares stable contracts: sorted names, matching predicates,
;; documentation/source output shape, root-cause traversal, and host-boundary
;; helper availability.

(require '[clojure.repl :as repl]
         '[clojure.string :as str])

(defn emit-case [case value]
  (println (pr-str {:case case :value value})))

(defn rejected? [f]
  (try
    (f)
    false
    (catch #?(:clj Throwable :lpy Exception) _ true)))

(defn repl-fixture-alpha
  "unique repl fixture alpha doc"
  [x]
  (inc x))

(defn repl-fixture-zebra
  "unique repl fixture zebra doc"
  []
  :zebra)

(defmacro repl-fixture-macro
  "unique repl fixture macro doc"
  []
  nil)

(defn nested-repl-exception []
  (try
    (throw (ex-info "inner repl cause" {:inner true}))
    (catch #?(:clj Throwable :lpy Exception) e
      (throw (ex-info "outer repl wrapper" {:outer true} e)))))

(defn fixture-names-from-apropos []
  (->> (repl/apropos "repl-fixture-")
       (map name)
       sort
       vec))

(emit-case :repl-public-portable-surface
           (every? #(contains? (ns-publics #?(:clj 'clojure.repl
                                              :lpy 'basilisp.repl))
                               %)
                   '[apropos
                     demunge
                     dir
                     dir-fn
                     doc
                     find-doc
                     pst
                     root-cause
                     set-break-handler!
                     source
                     source-fn
                     stack-element-str
                     thread-stopper]))

(emit-case :repl-search-and-dir
           (let [fixture-ns #?(:clj 'user :lpy 'basilisp.user)
                 dir-names (mapv str (repl/dir-fn fixture-ns))
                 dir-out   (str/split-lines
                            (with-out-str
                              (repl/dir #?(:clj user :lpy basilisp.user))))]
             {:apropos-names (fixture-names-from-apropos)
              :apropos-missing (empty? (repl/apropos "definitely-no-repl-match"))
              :dir-sorted? (= dir-names (vec (sort dir-names)))
              :dir-contains? (every? (set dir-names)
                                     ["repl-fixture-alpha"
                                      "repl-fixture-macro"
                                      "repl-fixture-zebra"])
              :dir-prints-dir-fn? (= dir-names dir-out)}))

(emit-case :repl-doc-and-find-doc
           (let [doc-out      (with-out-str (repl/doc repl-fixture-alpha))
                 macro-doc    (with-out-str (repl/doc repl-fixture-macro))
                 find-doc-out (with-out-str
                                (repl/find-doc "unique repl fixture alpha doc"))]
             {:doc-has-name? (str/includes? doc-out "repl-fixture-alpha")
              :doc-has-arglist? (str/includes? doc-out "[x]")
              :doc-has-text? (str/includes? doc-out "unique repl fixture alpha doc")
              :macro-doc-has-name? (str/includes? macro-doc "repl-fixture-macro")
              :macro-doc-has-marker? (str/includes? macro-doc "Macro")
              :find-doc-has-alpha? (str/includes? find-doc-out "repl-fixture-alpha")
              :find-doc-omits-zebra? (not (str/includes? find-doc-out
                                                          "repl-fixture-zebra"))
              :find-doc-invalid-rejected? (rejected? #(with-out-str
                                                        (repl/find-doc "[")))}))

(emit-case :repl-source-contracts
           {:missing-source-fn (nil? (repl/source-fn 'definitely-missing-symbol))
            :missing-source-output (str/trim-newline
                                     (with-out-str
                                       (repl/source definitely-missing-symbol)))
            :source-macro-direct-call? (var? #'repl/source)})

(emit-case :repl-stack-and-host-boundaries
           (try
             (nested-repl-exception)
             (catch #?(:clj Throwable :lpy Exception) e
               (let [root (repl/root-cause e)
                     pst-output (with-out-str (repl/pst e 1))
                     frame #?(:clj (first (.getStackTrace e))
                              :lpy (.-__traceback__ e))
                     rendered (repl/stack-element-str frame)]
                 {:root-message (ex-message root)
                  :pst-output-string? (string? pst-output)
                  :stack-element-string? (string? rendered)
                  :stack-element-non-empty? (pos? (count rendered))
                  :stack-element-has-parens? (and (boolean (re-find #"\(" rendered))
                                                  (boolean (re-find #"\)" rendered)))
                  :thread-stopper-zero-arity? (ifn? (repl/thread-stopper))
                  :thread-stopper-one-arity? (ifn? (repl/thread-stopper
                                                    #?(:clj (Thread/currentThread)
                                                       :lpy nil)))
                  :set-break-handler-fn? (ifn? repl/set-break-handler!)
                  :set-break-handler-var? (var? #'repl/set-break-handler!)}))))

(emit-case :repl-demunge
           [(repl/demunge "foo_bar_QMARK_")
            (repl/demunge "alpha_PLUS_beta_BANG_")])

(emit-case :basilisp-repl-extra-surface
           #?(:clj true
              :lpy (and (ifn? repl/mark-exception)
                        (ifn? repl/mark-repl-result)
                        (ifn? repl/print-doc)
                        (ifn? repl/print-source))))
