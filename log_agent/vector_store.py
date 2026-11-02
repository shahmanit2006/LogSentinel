import uuid
import pandas as pd
from qdrant_client import QdrantClient, models
from .embeddings import encode_texts


class LocalLogVectorStore:
    def __init__(self, path, collection, embedding_model, reset=False):
        self.client = QdrantClient(path=path)
        self.collection = collection
        self.embedding_model = embedding_model
        if reset:
            existing = [c.name for c in self.client.get_collections().collections]
            if self.collection in existing:
                self.client.delete_collection(self.collection)
        self._ensure_collection()

    def _ensure_collection(self):
        names = [c.name for c in self.client.get_collections().collections]
        if self.collection not in names:
            self.client.create_collection(
                collection_name=self.collection,
                vectors_config=models.VectorParams(size=384, distance=models.Distance.COSINE),
            )

    def index_dataframe(self, df, batch_size=128):
        if df.empty:
            return 0
        texts = [
            f"timestamp={r.timestamp}; simulation_time={getattr(r, 'simulation_time', None)}; level={r.level}; component={r.component}; hierarchy={getattr(r, 'hierarchy', '')}; uvm_id={getattr(r, 'uvm_id', '')}; error_category={getattr(r, 'error_category', '')}; message={r.message}; source={r.source}"
            for r in df.itertuples()
        ]
        vectors = encode_texts(texts, self.embedding_model)
        points = []
        for i, row in enumerate(df.to_dict("records")):
            payload = {
                "event_id": str(row["event_id"]),
                "timestamp": str(row["timestamp"]),
                "simulation_time": int(row["simulation_time"]) if pd.notna(row.get("simulation_time")) else None,
                "hierarchy": str(row.get("hierarchy", "")),
                "uvm_id": str(row.get("uvm_id", "")),
                "error_category": str(row.get("error_category", "")),
                "event_format": str(row.get("event_format", "standard")),
                "level": str(row["level"]),
                "component": str(row["component"]),
                "message": str(row["message"]),
                "raw": str(row["raw"]),
                "source": str(row["source"]),
                "line_no": int(row["line_no"]),
                "text": texts[i],
            }
            point_id = str(uuid.UUID(hex=str(row["event_id"])[:32]))
            points.append(models.PointStruct(id=point_id, vector=vectors[i].tolist(), payload=payload))
        for start in range(0, len(points), batch_size):
            self.client.upsert(collection_name=self.collection, points=points[start:start + batch_size], wait=True)
        return len(points)

    def search(self, query, top_k=8, component=None, level=None):
        vector = encode_texts([query], self.embedding_model)[0].tolist()
        must = []
        if component:
            must.append(models.FieldCondition(key="component", match=models.MatchValue(value=component)))
        if level:
            must.append(models.FieldCondition(key="level", match=models.MatchValue(value=level)))
        query_filter = models.Filter(must=must) if must else None
        result = self.client.query_points(
            collection_name=self.collection,
            query=vector,
            query_filter=query_filter,
            limit=int(top_k),
            with_payload=True,
        )
        return [{"score": round(float(p.score), 4), **(p.payload or {})} for p in result.points]

    def close(self):
        self.client.close()
