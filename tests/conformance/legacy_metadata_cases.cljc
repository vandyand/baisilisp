;; Legacy #^ metadata is still accepted by Clojure readers and appears in
;; older .clj/.cljc source. Compare only user metadata: Basilisp additionally
;; records source locations on reader forms.
(defn metadata-of [form]
  (select-keys (meta form) [:dynamic :doc :param-tags :tag]))

(println
 (pr-str
  {:case :legacy-metadata
   :value [(metadata-of '#^:dynamic legacy-var)
           (metadata-of '#^python/str typed-var)
           (metadata-of '#^{:doc "portable" :dynamic true} documented-var)
           (metadata-of '#^[:a python/str] parameterized-var)]}))
