(ns acceptance.data-priority-map.workflow
  (:require [clojure.data.priority-map :as pm]))

(def expected-publics
  ["->PersistentPriorityMap" "apply-keyfn" "priority->set-of-items"
   "priority-map" "priority-map-by" "priority-map-keyfn"
   "priority-map-keyfn-by" "rsubseq" "subseq"])

(defn error? [f]
  (try
    (f)
    false
    (catch #?(:clj Throwable :lpy python/Exception) _
      true)))

(defn publics []
  (set (map name (keys (ns-publics 'clojure.data.priority-map)))))

(defn contains-all? [actual expected]
  (every? actual expected))

(defn public-summary []
  {:surface (sort (publics))
   :contains-expected? (contains-all? (publics) expected-publics)})

(defn queue-summary []
  (let [p (pm/priority-map :a 2 :b 1 :c 3 :d 4)]
    {:entries (vec p)
     :peek (peek p)
     :pop (vec (pop p))
     :seq (vec (seq p))
     :rseq (vec (rseq p))
     :count (count p)
     :contains-b? (contains? p :b)
     :get-a (get p :a)
     :keys (vec (keys p))
     :vals (vec (vals p))
     :groups (pm/priority->set-of-items p)}))

(defn ordering-summary []
  {:ascending (vec (pm/priority-map :a 2 :b 1 :c 3))
   :descending (vec (pm/priority-map-by > :a 2 :b 1 :c 3))
   :keyfn (vec (pm/priority-map-keyfn first
                                      :a [2 :apple]
                                      :b [1 :banana]
                                      :c [3 :carrot]))
   :keyfn-desc (vec (pm/priority-map-keyfn-by first
                                              >
                                              :a [2 :apple]
                                              :b [1 :banana]
                                              :c [3 :carrot]))
   :keyfn-reprioritize (vec (assoc (pm/priority-map-keyfn first
                                                          :a [2 :apple]
                                                          :b [1 :banana])
                              :a [0 :apricot]))})

(defn bounds-summary []
  (let [p (pm/priority-map :a 2 :b 1 :c 3 :d 4 :e 5)]
    {:subseq-lt (vec (pm/subseq p < 3))
     :subseq-range (vec (pm/subseq p >= 2 < 4))
     :rsubseq-gte (vec (pm/rsubseq p >= 2))
     :rsubseq-range (vec (pm/rsubseq p <= 3 > 1))}))

(defn constructor-summary []
  (let [ascending (pm/->PersistentPriorityMap
                   (sorted-map 1 #{:b} 2 #{:c} 3 #{:a})
                   {:a [3 :apple] :b [1 :banana] :c [2 :carrot]}
                   {:origin :ctor}
                   first)
        descending (pm/->PersistentPriorityMap
                    (sorted-map-by > 1 #{:a} 3 #{:b} 2 #{:c})
                    {:a 1 :b 3 :c 2}
                    nil
                    nil)
        keyfn first]
    {:ascending {:entries (vec ascending)
                 :peek (peek ascending)
                 :meta (meta ascending)
                 :assoc (vec (assoc ascending :d [0 :date]))
                 :groups (pm/priority->set-of-items ascending)}
     :descending {:entries (vec descending)
                  :peek (peek descending)}
     :apply-keyfn [(pm/apply-keyfn [7 :seven])
                   (let [keyfn nil]
                     (pm/apply-keyfn [7 :seven]))]}))

(defn update-summary []
  (let [p (pm/priority-map :a 2 :b 1 :c 3)
        p2 (-> p
               (assoc :d 0)
               (assoc :a 4)
               (dissoc :b))
        conjed (conj (pm/priority-map) [:a 2] [:b 1])]
    {:assoc-dissoc (vec p2)
     :peek-after-updates (peek p2)
     :pop-after-updates (vec (pop p2))
     :conj (vec conjed)
     :empty-natural (vec (empty p))
     :empty-keyfn (vec (empty (pm/priority-map-keyfn first :a [1 :apple])))
     :into (vec (into (pm/priority-map) [[:z 3] [:x 1] [:y 2]]))
     :equiv-map? (= {:a 2 :b 1 :c 3} p)}))

(defn boundary-summary []
  {:odd-args (error? #(pm/priority-map :a 1 :b))
   :odd-args-by (error? #(pm/priority-map-by < :a 1 :b))
   :odd-args-keyfn (error? #(pm/priority-map-keyfn first :a [1 :apple] :b))
   :odd-args-keyfn-by (error? #(pm/priority-map-keyfn-by first < :a [1 :apple] :b))
   :empty-pop (error? #(pop (pm/priority-map)))
   :empty-peek (peek (pm/priority-map))})

(defn next-seed [seed]
  (mod (+ (* seed 1103515245) 12345) 2147483648))

(defn generated-key [seed]
  (keyword (str "k" (mod seed 13))))

(defn generated-indexed-key [index seed]
  (keyword (str "k" index "-" (mod seed 13))))

(defn generated-priority [seed]
  (mod seed 17))

(defn generated-pairs [seed n]
  (loop [remaining n
         index 0
         current seed
         result []]
    (if (zero? remaining)
      result
      (let [s1 (next-seed current)
            s2 (next-seed s1)]
        (recur (dec remaining)
               (inc index)
               s2
               ;; Equal-priority item order is backed by host set iteration in
               ;; data.priority-map, so generated cases use unique priorities.
               (conj result [(generated-indexed-key index s1)
                             (+ (* index 17) (generated-priority s2))]))))))

(defn generated-keyfn-pairs [seed n]
  (mapv (fn [[k v]] [k [v (keyword (str "v" v))]])
        (generated-pairs seed n)))

(defn queue-from-pairs [pairs]
  (apply pm/priority-map (mapcat identity pairs)))

(defn keyfn-queue-from-pairs [pairs]
  (apply pm/priority-map-keyfn first (mapcat identity pairs)))

(defn generated-case [seed]
  (let [size (+ 3 (mod seed 7))
        pairs (generated-pairs seed size)
        keyfn-pairs (generated-keyfn-pairs (next-seed seed) size)
        p (queue-from-pairs pairs)
        k (generated-key (next-seed (next-seed seed)))
        updated (assoc p k (+ 10000
                              (generated-priority
                               (next-seed (next-seed (next-seed seed))))))
        keyed (keyfn-queue-from-pairs keyfn-pairs)]
    {:seed seed
     :size (count p)
     :entries (vec p)
     :peek (peek p)
     :pop-count (count (pop p))
     :updated (vec updated)
     :groups (pm/priority->set-of-items p)
     :subseq (vec (pm/subseq p < 9))
     :rsubseq (vec (pm/rsubseq p >= 8))
     :keyfn-entries (vec keyed)
     :keyfn-peek (peek keyed)
     :next-seed (next-seed (next-seed (next-seed (next-seed seed))))}))

(defn generated-summary []
  (loop [remaining 96
         seed 424242
         result []]
    (if (zero? remaining)
      result
      (let [case (generated-case seed)]
        (recur (dec remaining)
               (:next-seed case)
               (conj result (dissoc case :next-seed)))))))
