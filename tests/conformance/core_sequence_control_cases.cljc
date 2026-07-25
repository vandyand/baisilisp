;; Portable clojure.core sequence/control/transducer helper semantics. Cases
;; avoid host object identity and random output, and normalize lazy outputs to
;; ordinary vectors for differential comparison.

(defn emit-case [case value]
  (println (pr-str {:case case :value value})))

(defn next-seed [seed]
  (mod (+ (* seed 1103515245) 12345) 2147483648))

(defn seeded-vector [seed]
  (loop [remaining (+ 3 (mod seed 6))
         current seed
         result []]
    (if (zero? remaining)
      result
      (let [next (next-seed current)]
        (recur (dec remaining)
               next
               (conj result (- (mod next 11) 5)))))))

(emit-case :control-and-lazy-sequence-helpers
           {:while (let [counter (atom 0)
                         seen (atom [])]
                     [(while (< @counter 5)
                        (swap! seen conj @counter)
                        (swap! counter inc))
                      @counter
                      @seen])
            :trampoline [(trampoline (fn step [n acc]
                                       (if (zero? n)
                                         acc
                                         #(step (dec n) (+ acc n))))
                                     6
                                     0)
                         (trampoline (fn [] :done))
                         (trampoline identity :value)]
            :lazy-cat (let [events (atom [])
                            xs (lazy-cat (do (swap! events conj :first)
                                             [1 2])
                                         (do (swap! events conj :second)
                                             [])
                                         (do (swap! events conj :third)
                                             [3 4]))]
                        [@events
                         (first xs)
                         @events
                         (vec xs)
                         @events])})

(emit-case :tree-seq-and-sorted-subseq
           {:tree [(vec (tree-seq sequential?
                                  seq
                                  [1 [2 3] [4 [5]]]))
                   (vec (tree-seq map?
                                   vals
                                   (sorted-map
                                    :root (sorted-map
                                           :left 1
                                           :right (sorted-map :leaf 2)))))]
            :subseq [(vec (subseq (sorted-map :a 1 :b 2 :c 3 :d 4)
                                  >= :b))
                     (vec (subseq (sorted-map :a 1 :b 2 :c 3 :d 4)
                                  >= :b < :d))
                     (vec (subseq (sorted-set :a :b :c :d)
                                  > :a <= :c))]
            :rsubseq [(vec (rsubseq (sorted-map :a 1 :b 2 :c 3 :d 4)
                                    <= :c))
                      (vec (rsubseq (sorted-map :a 1 :b 2 :c 3 :d 4)
                                    >= :b < :d))
                      (vec (rsubseq (sorted-set :a :b :c :d)
                                    > :a <= :c))]})

(emit-case :eduction-and-cat-transducer-boundaries
           (let [calls (atom 0)
                 xf (comp (map (fn [x]
                                 (swap! calls inc)
                                 (inc x)))
                          (filter odd?)
                          (take 3))
                 e (eduction xf (range))]
             {:eduction [(vec e)
                         @calls
                         (vec e)
                         @calls
                         (vec (eduction (mapcat identity)
                                        (filter odd?)
                                        [[0 1] [2 3] [4 5]]))]
              :cat [(vec (sequence cat [[1 2] [] [3 4]]))
                    (vec (sequence (comp cat (take 4))
                                   [[1 2 3] [4 5] [6]]))
                    (transduce cat conj [] [[1 2] [] [3]])
                    (transduce (comp cat (map inc)) conj [] [[1 2] [3]])
                    (let [rf (cat conj)]
                      [(rf)
                       (rf [:seed])
                       (rf [:seed] [1 2 3])])]}))

(emit-case :seeded-sequence-control-fuzz
           (mapv (fn [seed]
                   (let [values (seeded-vector seed)
                         nested [(take 2 values)
                                 (drop 2 values)]]
                     {:input values
                      :trampoline (trampoline (fn step [xs acc]
                                                (if (seq xs)
                                                  #(step (rest xs) (+ acc (first xs)))
                                                  acc))
                                              values
                                              0)
                      :tree (vec (tree-seq sequential? seq nested))
                      :cat (vec (sequence cat nested))
                      :eduction (vec (eduction (filter neg?)
                                               (map unchecked-inc)
                                               values))
                      :subseq (vec (subseq (apply sorted-set values)
                                           >= -2 <= 2))
                      :rsubseq (vec (rsubseq (apply sorted-set values)
                                             >= -2 <= 2))}))
                 (take 24 (iterate next-seed 94673821))))

(defn normalize-output [x]
  (cond
    (map? x) (into (sorted-map)
                   (map (fn [[k v]] [k (normalize-output v)]) x))
    (set? x) (vec (sort (map normalize-output x)))
    (sequential? x) (vec (map normalize-output x))
    :else x))

(defn seeded-xf [seed]
  (case (mod seed 10)
    0 (map #(+ % (mod seed 5)))
    1 (filter #(not (zero? (mod (+ % seed) 3))))
    2 (keep #(when (odd? (+ % seed)) (* % 2)))
    3 (map-indexed (fn [idx value] [idx value]))
    4 (keep-indexed (fn [idx value] (when (even? idx) [idx value])))
    5 (comp (drop (mod seed 4))
            (take (+ 1 (mod seed 5))))
    6 (comp (take-while #(< % (+ 3 (mod seed 5))))
            (map unchecked-inc))
    7 (partition-all (+ 1 (mod seed 3)))
    8 (partition-by #(neg? %))
    (comp (map #(- % (mod seed 3)))
          (dedupe)
          (take 5))))

(defn transducer-law-row [seed]
  (let [values (seeded-vector seed)
        xf (seeded-xf seed)
        sequence-output (normalize-output (sequence xf values))
        into-output (normalize-output (into [] xf values))
        transduce-output (normalize-output (transduce xf conj [] values))]
    {:seed seed
     :input values
     :sequence sequence-output
     :into into-output
     :transduce transduce-output
     :consistent? (= sequence-output into-output transduce-output)}))

(defn logging-xf
  [events]
  (fn [rf]
    (fn
      ([] (swap! events conj :init) (rf))
      ([result]
       (swap! events conj :complete)
       (rf result))
      ([result input]
       (swap! events conj [:step input])
       (rf result input)))))

(emit-case :adversarial-transducer-composition-laws
           (let [stateful-xf (comp (map-indexed (fn [idx value] [idx value]))
                                   (keep (fn [[idx value]]
                                           (when-not (= value :skip)
                                             [idx value])))
                                   (take-while #(not= [3 :stop] %)))
                 halt-events (atom [])
                 halt-rf (fn
                           ([] (swap! halt-events conj :init) [])
                           ([result]
                            (swap! halt-events conj :complete)
                            (conj result :done))
                           ([result input]
                            (swap! halt-events conj [:step input])
                            (conj result input)))]
            {:stateful [(vec (sequence stateful-xf
                                        [:a :skip :b :stop :c]))
                        (into [] stateful-xf [:a :skip :b :stop :c])]
              :completion [(let [events (atom [])
                                 output (vec (sequence (logging-xf events)
                                                       []))]
                             [output (= [:complete] @events)])
                           (let [events (atom [])]
                             (= [:a :b]
                                (vec (take 2
                                           (sequence (logging-xf events)
                                                     [:a :b :c :d])))))
                           (let [events (atom [])]
                             (empty?
                              (vec (sequence (comp (logging-xf events)
                                                   (take 0))
                                             [:a :b :c]))))]
              :halt-when [(transduce (halt-when #(= % 3)
                                                (fn [result input]
                                                  (conj result [:halt input])))
                                      halt-rf
                                      []
                                      [1 2 3 4])
                          @halt-events]
              :partition-completion [(mapv vec
                                           (sequence (partition-all 3)
                                                     [0 1 2 3 4]))
                                     (mapv vec
                                           (partition-all 3 2
                                                          [0 1 2 3 4]))
                                     (mapv vec
                                           (sequence (partition-by odd?)
                                                     [1 3 2 4 5 7 8]))
                                     (mapv vec
                                           (sequence
                                            (comp (partition-all 2)
                                                  (take 2))
                                            [0 1 2 3 4]))]
              :seeded-laws (mapv transducer-law-row
                                 (take 48
                                       (iterate next-seed 20260725)))}))
