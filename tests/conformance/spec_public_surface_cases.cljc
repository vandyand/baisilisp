;; Portable clojure.spec.alpha / clojure.spec.test.alpha public helper surface.
;;
;; This fixture avoids opaque spec object printing and checks only portable
;; values that both hosts can represent.

(require '[clojure.spec.alpha :as s]
         '[clojure.spec.test.alpha :as st])

(defn emit-case [case value]
  (println (pr-str {:case case :value value})))

(emit-case :spec-alpha-public-surface
           (every? #(contains? (ns-publics #?(:clj 'clojure.spec.alpha
                                              :lpy 'basilisp.spec.alpha))
                               %)
                   '[*coll-check-limit*
                     *coll-error-limit*
                     *explain-out*
                     *fspec-iterations*
                     *recursion-limit*
                     Spec
                     Specize
                     abbrev
                     alt-impl
                     amp-impl
                     and-spec-impl
                     cat-impl
                     conform*
                     def-impl
                     describe*
                     every-impl
                     explain*
                     explain-data*
                     explain-printer
                     fspec-impl
                     gen*
                     keys*
                     map-spec-impl
                     maybe-impl
                     merge-spec-impl
                     multi-spec-impl
                     nilable-impl
                     or-spec-impl
                     regex-spec-impl
                     registry
                     rep+impl
                     rep-impl
                     spec-impl
                     specize*
                     tuple-impl
                     unform*
                     with-gen*]))

(emit-case :spec-test-public-surface
           (every? #(contains? (ns-publics #?(:clj 'clojure.spec.test.alpha
                                              :lpy 'basilisp.spec.test.alpha))
                               %)
                   '[->sym
                     abbrev-result
                     check-fn
                     checkable-syms
                     enumerate-namespace
                     instrumentable-syms
                     summarize-results
                     with-instrument-disabled]))

(s/def :tests.spec-public/int int?)

(emit-case :spec-protocol-and-registry
           (let [sp (s/spec int?)]
             {:spec? (boolean (s/spec? sp))
              :conform (s/conform* sp 1)
              :invalid? (s/invalid? (s/conform* sp "x"))
              :explain? (boolean (s/explain-data* sp [] [] [] "x"))
              :registry? (contains? (s/registry) :tests.spec-public/int)}))

(emit-case :regex-impl-helpers
           {:cat (s/conform (s/cat-impl [:x] [int?] ['int?]) [1])
            :alt (s/conform (s/alt-impl [:i] [int?] ['int?]) [1])
            :rep+ (s/conform (s/rep+impl 'int? int?) [1 2])
            :maybe (s/conform (s/maybe-impl int? 'int?) [])})

(emit-case :spec-test-helpers
           {:sym (st/->sym 'clojure.core/+)
            :summary (st/summarize-results [])})
