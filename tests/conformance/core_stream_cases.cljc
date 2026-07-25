;; Portable clojure.core stream helper semantics. JVM streams and Python
;; iterators are host-specific one-shot inputs, so fixtures normalize creation
;; while comparing terminal operation results and overconsumption boundaries.

#?(:clj (import '[java.util Spliterators]
                'java.util.stream.StreamSupport))

(defn emit-case [case value]
  (println (pr-str {:case case :value value})))

(defn stream-from [xs]
  #?(:clj (.stream (vec xs))
     :lpy (python/iter xs)))

(defn iterator-from [xs]
  #?(:clj (.iterator (vec xs))
     :lpy (python/iter xs)))

(defn stream-from-iterator [it]
  #?(:clj (StreamSupport/stream
           (Spliterators/spliteratorUnknownSize it 0)
           false)
     :lpy it))

(defn iterator-next [it]
  #?(:clj (.next it)
     :lpy (python/next it)))

(emit-case :stream-basic-terminal-contracts
           {:seq [(vec (stream-seq! (stream-from [])))
                  (vec (stream-seq! (stream-from [1 2 3])))]
            :reduce [(stream-reduce! + (stream-from [1 2 3]))
                     (stream-reduce! + 10 (stream-from [1 2 3]))
                     (stream-reduce! (fn [] :empty) (stream-from []))]
            :transduce [(stream-transduce! (map inc) + (stream-from [1 2]))
                        (stream-transduce! (map inc) + 0 (stream-from [1 2 3]))]
            :into [(stream-into! [] (stream-from [1 2 3]))
                   (stream-into! [] (map inc) (stream-from [1 2 3]))
                   (vec (stream-into! (sorted-set) (stream-from [3 1 2])))]})

(emit-case :stream-one-shot-laziness-and-early-termination
           (let [seq-it (iterator-from [10 20 30])
                 seq-result (stream-seq! (stream-from-iterator seq-it))
                 reduce-it (iterator-from [0 1 2 3 4])
                 transduce-it (iterator-from [1 2 3 4 5])]
             {:seq [(first seq-result)
                    (vec seq-result)]
              :reduce [(stream-reduce! (fn [acc value]
                                         (if (= value 2)
                                           (reduced (+ acc value))
                                           (+ acc value)))
                                       0
                                       (stream-from-iterator reduce-it))
                       (iterator-next reduce-it)]
              :transduce [(stream-transduce! (take 2)
                                             +
                                             0
                                             (stream-from-iterator transduce-it))
                          (iterator-next transduce-it)]}))

(emit-case :stream-into-metadata-and-target-contracts
           (let [target (with-meta [] {:source :stream})
                 into-result (stream-into! target (stream-from [1 2 3]))]
             {:metadata [(vec into-result)
                         (meta into-result)]
              :list-target (stream-into! '(:z) (stream-from [:a :b]))
              :set-target (stream-into! #{} (stream-from [:a :b :a]))
              :xform-target (stream-into! []
                                           (comp (map #(* 2 %))
                                                 (filter #(> % 4)))
                                           (stream-from [1 2 3 4]))}))

(emit-case :stream-seeded-reduction-fuzz
           (mapv (fn [n]
                   (let [xs (mapv #(- (* n %) %) (range 8))
                         stop (mod (+ (* n 3) 2) (count xs))
                         reduce-it (iterator-from xs)]
                     {:n n
                      :xs xs
                      :seq (vec (stream-seq! (stream-from xs)))
                      :reduce (stream-reduce! + 0 (stream-from xs))
                      :reduce-no-init (stream-reduce! + (stream-from xs))
                      :early (let [result (stream-reduce!
                                           (fn [acc value]
                                             (let [idx (count acc)
                                                   next-acc (conj acc value)]
                                               (if (= idx stop)
                                                 (reduced next-acc)
                                                 next-acc)))
                                           []
                                           (stream-from-iterator reduce-it))
                                   next-value (when (< stop (dec (count xs)))
                                                (iterator-next reduce-it))]
                               [result next-value])
                      :transduce (stream-transduce! (comp (map inc)
                                                          (filter odd?))
                                                    conj
                                                    []
                                                    (stream-from xs))
                      :into (stream-into! []
                                           (map #(+ % n))
                                           (stream-from xs))}))
                 (range 1 8)))
