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
     alts! timeout pipe pipeline})

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
