;; Reader-conditionals isolate the standard-namespace substitutions required
;; for this library. The public functions themselves are portable source.
(ns acceptance.portable-library.util
  #?(:clj (:require [clojure.set :as set]
                    [clojure.string :as str]
                    [clojure.walk :as walk])
     :lpy (:require [basilisp.set :as set]
                    [basilisp.string :as str]
                    [basilisp.walk :as walk])))

(defn normalize-id [value]
  (-> value str/trim str/lower-case))

(defn index-by-id [entries]
  (into {}
        (map (fn [entry]
               [(keyword (normalize-id (:id entry))) entry])
             entries)))

(defn visible-ids [entries blocked]
  (->> entries
       (map :id)
       (map normalize-id)
       (remove blocked)
       set))

(defn visible-titles [entries blocked]
  (into []
        (comp (filter (fn [entry] (not (blocked (normalize-id (:id entry))))))
              (map (comp str/upper-case :title)))
        entries))

(defn keywordize-string-keys [value]
  (walk/postwalk
   (fn [item]
     (if (map? item)
       (into {} (map (fn [[key value]]
                       [(if (string? key) (keyword key) key) value])
                     item))
       item))
   value))
