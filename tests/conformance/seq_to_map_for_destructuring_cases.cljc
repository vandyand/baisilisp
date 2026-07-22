;; Clojure 1.11's keyword-argument sequence helper retains singleton values,
;; turns longer even sequences into maps, and rejects malformed odd sequences.

(ns conformance.seq-to-map-for-destructuring-cases)

(defn emit-case [case value]
  (println (pr-str {:case case :value value})))

(defn errors? [f]
  (try
    (f)
    false
    (catch Exception _ true)))

(emit-case :sequence-conversion
           {:nil? (= {} (seq-to-map-for-destructuring nil))
            :empty? (= {} (seq-to-map-for-destructuring []))
            :singleton? (= :key (seq-to-map-for-destructuring [:key]))
            :pairs? (= {:a 1 :b 2}
                       (seq-to-map-for-destructuring [:a 1 :b 2]))
            :characters? (= {\a \b} (seq-to-map-for-destructuring "ab"))
            :odd-rejected? (errors? #(seq-to-map-for-destructuring [:a 1 :b]))})
