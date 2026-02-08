import ast
import sys
from typing import Any

import dash
import numpy as np
import pandas as pd  # pyright: ignore[reportMissingTypeStubs]
import plotly.express as px  # pyright: ignore[reportMissingTypeStubs]
import umap  # pyright: ignore[reportMissingTypeStubs]
from dash import Input, Output, dcc, html
from result import Err

from rtfm_rag.services.database_service import get_database_connection

app = dash.Dash(__name__)


def setup_data() -> None:
  conn_result = get_database_connection()
  if isinstance(conn_result, Err):
    print(conn_result.err())
    sys.exit(1)
  conn = conn_result.ok()

  cur = conn.cursor()
  cur.execute("""
        SELECT c.id, c.content, c.embedding, c.url, c.index_id, i.name as index_name
        FROM chunks c
        JOIN indexes i ON c.index_id = i.id
    """)
  rows = cur.fetchall()
  cur.close()
  conn.close()

  df = pd.DataFrame(
    rows,
    columns=["id", "content", "embedding", "url", "index_id", "index_name"],  # type: ignore  # pyright: ignore[reportArgumentType]
  )
  df["embedding"] = df["embedding"].apply(
    lambda x: np.array(ast.literal_eval(x), dtype=np.float32)  # pyright: ignore[reportUnknownLambdaType, reportUnknownArgumentType]
  )
  embeddings = np.stack(df["embedding"].values)  # type: ignore  # pyright: ignore[reportUnknownVariableType, reportCallIssue, reportArgumentType]

  # Dimensionality reduction
  reducer = umap.UMAP(n_components=3, random_state=42)
  embedding_3d = reducer.fit_transform(embeddings)  # pyright: ignore[reportUnknownVariableType, reportUnknownArgumentType]
  df["x"] = embedding_3d[:, 0]  # type: ignore  # pyright: ignore[reportArgumentType, reportIndexIssue, reportCallIssue]
  df["y"] = embedding_3d[:, 1]  # type: ignore  # pyright: ignore[reportArgumentType, reportIndexIssue, reportCallIssue]
  df["z"] = embedding_3d[:, 2]  # type: ignore  # pyright: ignore[reportArgumentType, reportIndexIssue, reportCallIssue]

  fig = px.scatter_3d(
    df,
    x="x",
    y="y",
    z="z",
    color="index_name",
    hover_data=["content", "url"],
    title="Chunks in Embedding Space",
  )

  fig.update_layout(
    paper_bgcolor="#332726",
    plot_bgcolor="#332726",
    scene={
      "xaxis": {"backgroundcolor": "#332726"},
      "yaxis": {"backgroundcolor": "#332726"},
      "zaxis": {"backgroundcolor": "#332726"},
    },
  )

  app.layout = html.Div(
    [
      html.H2("3D Embedding Explorer"),
      dcc.Graph(
        id="embedding-3d",
        figure=fig,
        style={"height": "80vh"},
      ),
      html.Div(id="chunk-info", style={"marginTop": 20}),
    ],
    style={"backgroundColor": "#332726"},
  )


@app.callback(Output("chunk-info", "children"), Input("embedding-3d", "clickData"))
def display_chunk_info(clickData: Any) -> html.Div | str:
  if clickData and "points" in clickData:
    point = clickData["points"][0]
    content = point["customdata"][0]
    url = point["customdata"][1]
    return html.Div(
      [
        html.H4("Chunk Details"),
        html.P(content),
        html.A("Source", href=url, target="_blank"),
      ]
    )
  return "Click a point to see details."


if __name__ == "__main__":
  setup_data()
  app.run(debug=True)
