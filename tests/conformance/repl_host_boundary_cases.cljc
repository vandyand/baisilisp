;; Portable clojure.repl/basilisp.repl host-boundary cases.
;;
;; JVM thread stopping, debugger break handlers, and StackTraceElement classes
;; are host-specific. These cases lock the public names and portable
;; stack-element string contract without requiring identical host frame text.

(require '[clojure.repl :as repl])

(defn emit-case [case value]
  (println (pr-str {:case case :value value})))

(defn stack-summary []
  #?(:clj (first (.getStackTrace (Exception. "fixture")))
     :lpy (try
            (throw (python/RuntimeError "fixture"))
            (catch python/RuntimeError e
              (.-__traceback__ e)))))

(emit-case :public-host-boundary-surface
           (every? #(contains? (ns-publics #?(:clj 'clojure.repl
                                              :lpy 'basilisp.repl))
                               %)
                   '[set-break-handler!
                     stack-element-str
                     thread-stopper]))

(emit-case :stack-element-str-shape
           (let [rendered (repl/stack-element-str (stack-summary))]
             {:string? (string? rendered)
              :non-empty? (pos? (count rendered))
              :has-open-paren? (boolean (re-find #"\(" rendered))
              :has-close-paren? (boolean (re-find #"\)" rendered))}))
