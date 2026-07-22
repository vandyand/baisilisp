(ns conformance.chunk-cases)

(defn emit-case [case value]
  (println (pr-str {:case case :value value})))

(defn chunk-items [chunk]
  (mapv #(nth chunk %) (range (count chunk))))

(let [buffer (chunk-buffer 3)
      _ (chunk-append buffer :a)
      _ (chunk-append buffer :b)
      current (chunk buffer)
      chunk-seq (chunk-cons current (seq [:c :d]))
      vector-seq (seq (vec (range 40)))]
  (emit-case :chunk-contract
             {:chunk-items (chunk-items current)
              :append-returned-nil? (nil? (chunk-append (chunk-buffer 1) :x))
              :chunked? (chunked-seq? chunk-seq)
              :first-items (chunk-items (chunk-first chunk-seq))
              :partial-items (chunk-items (chunk-first (rest chunk-seq)))
              :rest-items (vec (chunk-rest chunk-seq))
              :next-items (vec (chunk-next chunk-seq))
              :sequence-items (vec chunk-seq)
              :buffer-closed? (try
                                (chunk-append buffer :late)
                                false
                                (catch Exception _ true))
              :vector-first (chunk-items (chunk-first vector-seq))
              :vector-next (chunk-items (chunk-first (chunk-next vector-seq)))
              :vector-partial (chunk-items (chunk-first (rest vector-seq)))
              :map-chunked? (chunked-seq? (seq (map identity [1 2])))
              :map-indexed-chunked?
              (chunked-seq? (seq (map-indexed vector [1 2])))
              :filter-chunked? (chunked-seq? (seq (filter odd? [1 2])))
              :keep-chunked? (chunked-seq? (seq (keep identity [1 2])))
              :keep-indexed-chunked?
              (chunked-seq? (seq (keep-indexed (fn [_ x] x) [1 2])))
              :concat-chunked? (chunked-seq? (seq (concat [1 2] [3])))
              :map-realization
              (let [seen (atom [])
                    output (map #(do (swap! seen conj %) %) (vec (range 40)))]
                (first output)
                @seen)}))
