using UnityEngine;

namespace BlockCraft;

/// <summary>
/// IMGUI feedback, same approach as the portal gun example (the game's notifications only
/// show on the suit's helmet HUD): a short centre message plus a Minecraft-style hotbar
/// with a preview swatch, the selected slot framed.
/// </summary>
public class BlockHud : MonoBehaviour
{
	public BlockTool Tool;

	private string _message;
	private float _messageUntil;
	private GUIStyle _style;

	public void Show(string text, float seconds = 2.5f)
	{
		_message = text;
		_messageUntil = Time.unscaledTime + seconds;
	}

	private void OnGUI()
	{
		if (Event.current.type != EventType.Repaint || OWTime.IsPaused())
			return;
		var s = Screen.height / 1080f;

		if (_message != null && Time.unscaledTime < _messageUntil && OWInput.IsInputMode(InputMode.Character))
		{
			_style ??= new GUIStyle(GUI.skin.label) { alignment = TextAnchor.MiddleCenter, fontSize = Mathf.RoundToInt(22 * s) };
			var rect = new Rect(0, Screen.height * 0.70f, Screen.width, 40 * s);
			var a = Mathf.Clamp01(_messageUntil - Time.unscaledTime);
			_style.normal.textColor = new Color(0, 0, 0, 0.8f * a);
			GUI.Label(new Rect(rect.x + 2, rect.y + 2, rect.width, rect.height), _message, _style);
			_style.normal.textColor = new Color(1, 1, 1, a);
			GUI.Label(rect, _message, _style);
		}

		if (Tool == null || !Tool.Equipped || !OWInput.IsInputMode(InputMode.Character))
			return;

		// Hotbar: six slots along the bottom, preview cube drawn as its top-face colour block.
		var n = BlockTextures.Names.Length;
		var slot = 54f * s;
		var total = slot * n + 8f * s * (n - 1);
		var x0 = (Screen.width - total) * 0.5f;
		var y0 = Screen.height - slot - 26f * s;
		for (var i = 0; i < n; i++)
		{
			var r = new Rect(x0 + i * (slot + 8f * s), y0, slot, slot);
			var old = GUI.color;
			GUI.color = new Color(0, 0, 0, 0.45f);
			GUI.DrawTexture(r, Texture2D.whiteTexture);
			GUI.color = Swatch((BlockType)i);
			var inner = new Rect(r.x + 5f * s, r.y + 5f * s, r.width - 10f * s, r.height - 10f * s);
			GUI.DrawTexture(inner, Texture2D.whiteTexture);
			if ((BlockType)i == Tool.Selected)
			{
				GUI.color = Color.white;
				var b = 3f * s;
				GUI.DrawTexture(new Rect(r.x - b, r.y - b, r.width + 2 * b, b), Texture2D.whiteTexture);
				GUI.DrawTexture(new Rect(r.x - b, r.y + r.height, r.width + 2 * b, b), Texture2D.whiteTexture);
				GUI.DrawTexture(new Rect(r.x - b, r.y, b, r.height), Texture2D.whiteTexture);
				GUI.DrawTexture(new Rect(r.x + r.width, r.y, b, r.height), Texture2D.whiteTexture);
			}
			GUI.color = old;
		}
		_style ??= new GUIStyle(GUI.skin.label) { alignment = TextAnchor.MiddleCenter, fontSize = Mathf.RoundToInt(22 * s) };
		_style.normal.textColor = Color.white;
		GUI.Label(new Rect(0, y0 - 34f * s, Screen.width, 30f * s), BlockTextures.Names[(int)Tool.Selected], _style);
	}

	private static Color Swatch(BlockType t) => t switch
	{
		BlockType.Grass => new Color(0.42f, 0.69f, 0.25f),
		BlockType.Dirt => new Color(0.53f, 0.38f, 0.26f),
		BlockType.Stone => new Color(0.5f, 0.5f, 0.5f),
		BlockType.Log => new Color(0.42f, 0.33f, 0.2f),
		BlockType.Planks => new Color(0.69f, 0.56f, 0.35f),
		BlockType.Leaves => new Color(0.22f, 0.46f, 0.15f),
		_ => Color.magenta
	};
}
