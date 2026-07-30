;; Portable checks for the currently implemented non-go clojure.core.async
;; compatibility facade.

(ns conformance.core-async-cases)

#?(:clj (require '[clojure.core.async :as async])
   :lpy (require '[clojure.core.async :as async]))

#?(:lpy (import asyncio))

(defn emit-case [case value]
  (println (pr-str {:case case :value value})))

(def supported-non-go-publics
  '#{buffer dropping-buffer sliding-buffer
     chan close! offer! poll! put! take!
     alts! timeout pipe pipeline
     to-chan! onto-chan! merge split take
     into reduce transduce})

(def unsupported-parking-and-blocking-publics
  '#{go go-loop <! >! alt!
     <!! >!! alts!! thread thread-call
     pub sub mult mix pipeline-async pipeline-blocking})

(defn current-publics []
  (set (keys (ns-publics 'clojure.core.async))))

(defn supported-public-surface []
  {:supported-present?   (every? (current-publics) supported-non-go-publics)
   :unsupported-absent-in-basilisp?  #?(:clj true
                            :lpy (not-any? (current-publics)
                                           unsupported-parking-and-blocking-publics))})

#?(:clj
   (defn to-chan-roundtrip []
     (let [channel (async/to-chan! [1 2 3])]
       [(async/<!! channel)
        (async/<!! channel)
        (async/<!! channel)
        (async/<!! channel)]))

   :lpy
   (defasync to-chan-roundtrip []
     (let [channel (async/to-chan! [1 2 3])]
       [(await (async/take! channel))
        (await (async/take! channel))
        (await (async/take! channel))
        (await (async/take! channel))])))

#?(:clj
   (defn onto-chan-roundtrip []
     (let [channel    (async/chan 2)
           completion (async/onto-chan! channel [:first :second])]
       (async/<!! completion)
       [(async/<!! channel)
        (async/<!! channel)
        (async/<!! channel)]))

   :lpy
   (defasync onto-chan-roundtrip []
     (let [channel    (async/chan 2)
           completion (async/onto-chan! channel [:first :second])]
       (await (async/take! completion))
       [(await (async/take! channel))
        (await (async/take! channel))
        (await (async/take! channel))])))

#?(:clj
   (defn merge-roundtrip []
     (let [first  (async/to-chan! [1 2])
           second (async/to-chan! [3])
           output (async/merge [first second] 3)]
       (sort [(async/<!! output)
              (async/<!! output)
              (async/<!! output)])))

   :lpy
   (defasync merge-roundtrip []
     (let [first  (async/to-chan! [1 2])
           second (async/to-chan! [3])
           output (async/merge [first second] 3)]
       (sort [(await (async/take! output))
              (await (async/take! output))
              (await (async/take! output))]))))

#?(:clj
   (defn split-roundtrip []
     (let [[even odd] (async/split even? (async/to-chan! [1 2 3 4]) 2 2)]
       [(async/<!! even)
        (async/<!! even)
        (async/<!! even)
        (async/<!! odd)
        (async/<!! odd)
        (async/<!! odd)]))

   :lpy
   (defasync split-roundtrip []
     (let [[even odd] (async/split even? (async/to-chan! [1 2 3 4]) 2 2)]
       [(await (async/take! even))
        (await (async/take! even))
        (await (async/take! even))
        (await (async/take! odd))
        (await (async/take! odd))
        (await (async/take! odd))])))

#?(:clj
   (defn take-roundtrip []
     (let [output (async/take 2 (async/to-chan! [1 2 3]) 2)]
       [(async/<!! output)
        (async/<!! output)
        (async/<!! output)]))

   :lpy
   (defasync take-roundtrip []
     (let [output (async/take 2 (async/to-chan! [1 2 3]) 2)]
       [(await (async/take! output))
        (await (async/take! output))
        (await (async/take! output))])))

#?(:clj
   (defn fold-roundtrip []
     [(async/<!! (async/into [] (async/to-chan! [1 2 3])))
      (async/<!! (async/reduce + 0 (async/to-chan! [1 2 3])))
      (async/<!! (async/transduce (map inc) + 0 (async/to-chan! [1 2 3])))])

   :lpy
   (defasync fold-roundtrip []
     [(await (async/take! (async/into [] (async/to-chan! [1 2 3]))))
      (await (async/take! (async/reduce + 0 (async/to-chan! [1 2 3]))))
      (await (async/take! (async/transduce (map inc) + 0 (async/to-chan! [1 2 3]))))]))

#?(:clj
   (defn fixed-buffer-roundtrip []
     (let [channel (async/chan (async/buffer 2))]
       (async/>!! channel :first)
       (async/>!! channel :second)
       [(async/<!! channel)
        (async/<!! channel)]))

   :lpy
   (defasync fixed-buffer-roundtrip []
     (let [channel (async/chan (async/buffer 2))]
       (await (async/put! channel :first))
       (await (async/put! channel :second))
       [(await (async/take! channel))
        (await (async/take! channel))])))

#?(:clj
   (defn sliding-buffer-roundtrip []
     (let [channel (async/chan (async/sliding-buffer 2))]
       (async/>!! channel :first)
       (async/>!! channel :second)
       (async/>!! channel :third)
       [(async/<!! channel)
        (async/<!! channel)]))

   :lpy
   (defasync sliding-buffer-roundtrip []
     (let [channel (async/chan (async/sliding-buffer 2))]
       (await (async/put! channel :first))
       (await (async/put! channel :second))
       (await (async/put! channel :third))
       [(await (async/take! channel))
        (await (async/take! channel))])))

#?(:clj
   (defn dropping-buffer-roundtrip []
     (let [channel (async/chan (async/dropping-buffer 2))]
       (async/>!! channel :first)
       (async/>!! channel :second)
       (async/>!! channel :third)
       [(async/<!! channel)
        (async/<!! channel)]))

   :lpy
   (defasync dropping-buffer-roundtrip []
     (let [channel (async/chan (async/dropping-buffer 2))]
       (await (async/put! channel :first))
       (await (async/put! channel :second))
       (await (async/put! channel :third))
       [(await (async/take! channel))
        (await (async/take! channel))])))

#?(:clj
   (defn close-drains-buffer-roundtrip []
     (let [channel (async/chan 1)]
       (async/>!! channel :buffered)
       (async/close! channel)
       [(async/<!! channel)
        (async/<!! channel)]))

   :lpy
   (defasync close-drains-buffer-roundtrip []
     (let [channel (async/chan 1)]
       (await (async/put! channel :buffered))
       (async/close! channel)
       [(await (async/take! channel))
        (await (async/take! channel))])))

#?(:clj
   (defn nil-put-rejected? []
     (let [channel (async/chan 1)]
       (try
         (async/>!! channel nil)
         false
         (catch Throwable _
           true))))

   :lpy
   (defasync nil-put-rejected? []
     (let [channel (async/chan 1)]
       (try
         (await (async/put! channel nil))
         false
         (catch Exception _
           true)))))

#?(:clj
   (defn alts-priority-and-default-roundtrip []
     (let [first  (async/chan 1)
           second (async/chan 1)]
       (async/>!! first :first)
       (async/>!! second :second)
       (let [[value selected] (async/alts!! [second first] :priority true)
             [fallback port]  (async/alts!! [(async/chan)] :default :fallback)]
         [value (identical? selected second) fallback port])))

   :lpy
   (defasync alts-priority-and-default-roundtrip []
     (let [first  (async/chan 1)
           second (async/chan 1)]
       (await (async/put! first :first))
       (await (async/put! second :second))
       (let [[value selected] (await (async/alts! [second first] :priority true))
             [fallback port]  (await (async/alts! [(async/chan)] :default :fallback))]
         [value (identical? selected second) fallback port]))))

#?(:clj
   (defn timeout-roundtrip []
     (async/<!! (async/timeout 1)))

   :lpy
   (defasync timeout-roundtrip []
     (await (async/take! (async/timeout 1)))))

#?(:clj
   (defn pipe-roundtrip []
     (let [source      (async/chan 2)
           destination (async/chan 2)]
       (async/>!! source :first)
       (async/>!! source :second)
       (async/close! source)
       (async/pipe source destination)
       [(async/<!! destination)
        (async/<!! destination)
        (async/<!! destination)]))

   :lpy
   (defasync pipe-roundtrip []
     (let [source      (async/chan 2)
           destination (async/chan 2)]
       (await (async/put! source :first))
       (await (async/put! source :second))
       (async/close! source)
       (await (async/pipe source destination))
       [(await (async/take! destination))
        (await (async/take! destination))
        (await (async/take! destination))])))

#?(:clj
   (defn pipeline-roundtrip []
     (let [source      (async/chan 3)
           destination (async/chan 3)]
       (async/>!! source 1)
       (async/>!! source 2)
       (async/>!! source 3)
       (async/close! source)
       (async/pipeline 2 destination (map inc) source)
       [(async/<!! destination)
        (async/<!! destination)
        (async/<!! destination)
        (async/<!! destination)]))

   :lpy
   (defasync pipeline-roundtrip []
     (let [source      (async/chan 3)
           destination (async/chan 3)]
       (await (async/put! source 1))
       (await (async/put! source 2))
       (await (async/put! source 3))
       (async/close! source)
       (await (async/pipeline 2 destination (map inc) source))
       [(await (async/take! destination))
        (await (async/take! destination))
        (await (async/take! destination))
        (await (async/take! destination))])))

(emit-case :core-async-public-surface
           (supported-public-surface))

(emit-case :core-async-buffers
           #?(:clj [(fixed-buffer-roundtrip)
                    (sliding-buffer-roundtrip)
                    (dropping-buffer-roundtrip)]
              :lpy [(asyncio/run (fixed-buffer-roundtrip))
                    (asyncio/run (sliding-buffer-roundtrip))
                    (asyncio/run (dropping-buffer-roundtrip))]))

(emit-case :core-async-close-and-nil
           #?(:clj [(close-drains-buffer-roundtrip)
                    (nil-put-rejected?)]
              :lpy [(asyncio/run (close-drains-buffer-roundtrip))
                    (asyncio/run (nil-put-rejected?))]))

(emit-case :core-async-selection-timeout-pipe-pipeline
           #?(:clj [(alts-priority-and-default-roundtrip)
                    (timeout-roundtrip)
                    (pipe-roundtrip)
                    (pipeline-roundtrip)]
              :lpy [(asyncio/run (alts-priority-and-default-roundtrip))
                    (asyncio/run (timeout-roundtrip))
                    (asyncio/run (pipe-roundtrip))
                    (asyncio/run (pipeline-roundtrip))]))

(emit-case :core-async-collection-combinators
           #?(:clj [(to-chan-roundtrip)
                    (onto-chan-roundtrip)
                    (merge-roundtrip)
                    (split-roundtrip)
                    (take-roundtrip)
                    (fold-roundtrip)]
              :lpy [(asyncio/run (to-chan-roundtrip))
                    (asyncio/run (onto-chan-roundtrip))
                    (asyncio/run (merge-roundtrip))
                    (asyncio/run (split-roundtrip))
                    (asyncio/run (take-roundtrip))
                    (asyncio/run (fold-roundtrip))]))
