(ns acceptance.portable-library.catalog
  (:require [acceptance.portable-library.util :as util]))

(defn summarize [entries blocked]
  (let [by-id (util/index-by-id entries)]
    {:ids (util/visible-ids entries blocked)
     :titles (into {}
                   (map (fn [[id entry]] [id (:title entry)]) by-id))
     :visible-titles (util/visible-titles entries blocked)
     :entry-count (count entries)}))

(defn decode-payload [payload]
  (if (map? payload)
    (util/keywordize-string-keys payload)
    (throw (ex-info "payload must be a map" {:value payload}))))
