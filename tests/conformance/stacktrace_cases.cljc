;; Portable clojure.stacktrace/basilisp.stacktrace cases. Stack frame file names
;; and host exception classes are intentionally not compared. Each case compares
;; stable stacktrace semantics: public surface, root-cause traversal, throwable
;; summaries, cause-vs-stack chaining, trace-element output, and seeded causal
;; chain depths.

#?(:clj (require '[clojure.stacktrace :as st]
                 '[clojure.string :as str])
   :lpy (require '[clojure.stacktrace :as st]
                 '[basilisp.string :as str]))

#?(:lpy (import [traceback :as tb]))

(defn emit-case [case value]
  (println (pr-str {:case case :value value})))

(defn public-stacktrace-names []
  (sort (map name (keys (ns-publics #?(:clj 'clojure.stacktrace
                                        :lpy 'basilisp.stacktrace))))))

(defn throw-chain [depth]
  (if (zero? depth)
    (throw (ex-info "leaf" {:depth depth}))
    (try
      (throw-chain (dec depth))
      (catch #?(:clj Throwable :lpy python/Exception) cause
        (throw (ex-info (str "node-" depth) {:depth depth} cause))))))

(defn capture-chain [depth]
  (try
    (throw-chain depth)
    (catch #?(:clj Throwable :lpy python/Exception) e
      e)))

(defn output-summary [s]
  {:has-leaf (str/includes? s "leaf")
   :has-node-2 (str/includes? s "node-2")
   :has-data (str/includes? s ":depth")
   :non-empty (not (str/blank? s))})

(defn trace-element [e]
  #?(:clj (first (.getStackTrace e))
     :lpy (first (tb/extract_tb (.-__traceback__ e)))))

(emit-case :public-surface
           (public-stacktrace-names))

(emit-case :root-cause
           (let [e (capture-chain 4)]
             {:root-message (ex-message (st/root-cause e))
              :outer-message (ex-message e)}))

(emit-case :throwable-output
           (output-summary (with-out-str
                             (st/print-throwable (capture-chain 2)))))

(emit-case :stack-vs-cause-output
           (let [e (capture-chain 2)
                 stack-output (with-out-str (st/print-stack-trace e 1))
                 cause-output (with-out-str (st/print-cause-trace e 1))]
             {:stack (output-summary stack-output)
              :cause (output-summary cause-output)
              :stack-excludes-root (not (str/includes? stack-output "leaf"))
              :cause-includes-root (str/includes? cause-output "leaf")}))

(emit-case :trace-element-output
           (let [line (with-out-str
                        (st/print-trace-element (trace-element (capture-chain 1))))]
             {:non-empty (not (str/blank? line))
              :has-location-delimiters (and (str/includes? line "(")
                                            (str/includes? line ")"))}))

(emit-case :seeded-root-cause-depths
           (mapv (fn [depth]
                   (let [e (capture-chain depth)]
                     {:depth depth
                      :root (ex-message (st/root-cause e))
                      :outer (ex-message e)}))
                 [0 1 2 3 5 8]))
