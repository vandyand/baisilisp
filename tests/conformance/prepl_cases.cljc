;; Portable clojure.core.server/basilisp.core.server pREPL event-envelope cases.
;; Output chunks may be split differently by host writers, so adjacent :out/:err
;; events are coalesced before comparison. Return event namespace, source form,
;; value, quit behavior, and io-prepl serialization are stable public contract.

#?(:clj (do
          (require '[clojure.core.server :as server]
                   '[clojure.string])
          (import '[clojure.lang LineNumberingPushbackReader]
                  '[java.io StringReader StringWriter PrintWriter]))
   :lpy (do
          (require '[clojure.core.server :as server]
                   '[clojure.string])
          (import io)))

(defn emit-case [case value]
  (println (pr-str {:case case :value value})))

(defn normalize-newlines [s]
  (clojure.string/replace s #"\r\n" "\n"))

(defn reader-for [source]
  #?(:clj (LineNumberingPushbackReader. (StringReader. source))
     :lpy (io/StringIO source)))

(defn normalize-event [event]
  (let [event (dissoc event :ms)]
    (if (#{:out :err} (:tag event))
      (update event :val normalize-newlines)
      event)))

(defn coalesce-stream-event [events event]
  (let [event (normalize-event event)
        previous (peek events)]
    (if (and previous
             (= (:tag previous) (:tag event))
             (#{:out :err} (:tag event)))
      (conj (pop events)
            (update previous :val str (:val event)))
      (conj events event))))

(defn normalized-events [events]
  (reduce coalesce-stream-event [] events))

(defn run-prepl [source]
  (let [events (atom [])]
    (server/prepl (reader-for source) #(swap! events conj %))
    (normalized-events @events)))

(defn run-io-prepl [source]
  #?(:clj (let [out (StringWriter.)]
            (binding [*in* (reader-for source)
                      *out* (PrintWriter. out true)]
              (server/io-prepl))
            (normalize-event (read-string (str out))))
     :lpy (let [out (io/StringIO)]
            (binding [*in* (reader-for source)
                      *out* out]
              (server/io-prepl))
            (normalize-event (read-string (.getvalue out))))))

(emit-case :prepl-default-namespace-and-output
           (run-prepl "(println \"hello\")\n(+ 1 2)\n"))

(emit-case :prepl-namespace-transition-and-quit
           (let [events (run-prepl "(ns prepl-fixture)\n(+ 2 3)\n:repl/quit\n(+ 9 9)\n")]
             (remove-ns 'prepl-fixture)
             events))

(emit-case :io-prepl-default-namespace
           (run-io-prepl "(+ 3 4)\n"))
